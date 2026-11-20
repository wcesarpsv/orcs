// Service credential stays inside Supabase's function runtime; never returned to the browser.
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}});
Deno.serve(async(req:Request)=>{
 if(req.method!=='POST')return json({error:'Method not allowed.'},405);
 const auth=req.headers.get('Authorization')||'';
 if(!auth.startsWith('Bearer '))return json({error:'Sign in first.'},401);
 const base=Deno.env.get('SUPABASE_URL')!,publicKey=Deno.env.get('SUPABASE_ANON_KEY')!,service=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
 const headers={apikey:publicKey,Authorization:auth,'Content-Type':'application/json'};
 try{
  const who=await fetch(base+'/auth/v1/user',{headers});if(!who.ok)return json({error:'Session expired.'},401);
  const user=await who.json();
  const check=await fetch(base+'/rest/v1/rpc/orcs_manage_users',{method:'POST',headers,body:JSON.stringify({p_action:'me'})});
  if(!check.ok)return json({error:'Active administrator access required.'},403);
  const member=await check.json();if(!['owner','admin'].includes(member.role))return json({error:'Administrator access required.'},403);
  const body=await req.json();const email=typeof body.email==='string'?body.email.trim().toLowerCase():'';const role=body.role;
  if(email.length>254||!/^\S+@[^\s@]+\.[^\s@]+$/.test(email)||!['technician','admin'].includes(role))return json({error:'Enter a valid email and select Technician or Admin.'},400);
  const privileged={apikey:service,Authorization:'Bearer '+service,'Content-Type':'application/json'};
  const invite=await fetch(base+'/auth/v1/invite?redirect_to='+encodeURIComponent('https://orcs-reports.vercel.app/account'),{method:'POST',headers:privileged,body:JSON.stringify({email})});
  if(!invite.ok){if(invite.status===429)return json({error:'Email rate limit reached. Wait before trying again.'},429);return json({error:'Could not invite this address. It may already have an account. Existing access can only be changed by the owner.'},400)}
  const invited=await invite.json();
  const grant=await fetch(base+'/rest/v1/rpc/orcs_provision_user',{method:'POST',headers:privileged,body:JSON.stringify({p_actor:user.id,p_target:invited.id,p_role:role})});
  if(!grant.ok)return json({error:'Invitation sent, but access approval was not completed. Ask the owner to review this account in Supabase before retrying.'},409);
  return json({ok:true,message:'Invitation sent. The account is approved as '+role+'.'});
 }catch{return json({error:'Account service unavailable. Check the users list before retrying.'},502)}
});
