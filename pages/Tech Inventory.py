import streamlit as st
import sqlite3
from datetime import datetime, date
import pandas as pd
from streamlit_qrcode_scanner import qrcode_scanner

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="Field Inventory Tracker", layout="wide")
DB_PATH = "inventory.db"

# =========================
# DB HELPERS
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS technicians (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        email TEXT,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS item_types (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number TEXT NOT NULL UNIQUE,
        asset_tag TEXT,
        item_type_id INTEGER NOT NULL,
        description TEXT,
        status TEXT NOT NULL, -- AVAILABLE / IN_FIELD / INSTALLED / LOST / DAMAGED
        created_at TEXT NOT NULL,
        FOREIGN KEY(item_type_id) REFERENCES item_types(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL,
        technician_id INTEGER NOT NULL,
        request_date TEXT,
        issued_date TEXT,
        installed_date TEXT,
        returned_date TEXT,
        location_place_name TEXT,
        rdl TEXT,
        notes TEXT,
        closed INTEGER NOT NULL DEFAULT 0, -- 0 open, 1 closed
        created_at TEXT NOT NULL,
        FOREIGN KEY(item_id) REFERENCES items(id),
        FOREIGN KEY(technician_id) REFERENCES technicians(id)
    );
    """)

    cur.execute("""
    CREATE INDEX IF NOT EXISTS idx_assignments_open
    ON assignments(closed, technician_id, item_id);
    """)

    conn.commit()
    conn.close()

def qdf(query, params=None):
    conn = get_conn()
    df = pd.read_sql_query(query, conn, params=params or {})
    conn.close()
    return df

def exec_sql(query, params=None):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(query, params or {})
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id

def to_iso(d):
    if d is None:
        return None
    if isinstance(d, (datetime, date)):
        return d.isoformat()
    return str(d)

def today_str():
    return date.today().isoformat()

def status_badge(status: str) -> str:
    m = {
        "AVAILABLE": "🟢 AVAILABLE",
        "IN_FIELD": "🟡 IN_FIELD",
        "INSTALLED": "🔵 INSTALLED",
        "LOST": "🔴 LOST",
        "DAMAGED": "🟠 DAMAGED",
    }
    return m.get(status, status)

# =========================
# INIT
# =========================
init_db()

st.title("🧰 Field Inventory Tracker (SST / Carmanah / Tools)")
st.caption("Cadastro de técnicos + itens via scanner (câmera traseira) + movimentações (request → issued → installed → returned).")

tabs = st.tabs([
    "📌 Friday Check",
    "👤 Technicians",
    "📦 Item Types",
    "🧾 Items (Scan SN)",
    "🔁 Assignments",
    "📤 Export"
])

# =========================
# TAB 0: Friday Check
# =========================
with tabs[0]:
    st.subheader("📌 Friday Check (itens em posse / em andamento)")

    techs = qdf("SELECT id, name FROM technicians WHERE active=1 ORDER BY name;")
    items_in_field = qdf("""
        SELECT
            a.id AS assignment_id,
            t.name AS technician,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.status,
            a.request_date,
            a.issued_date,
            a.installed_date,
            a.location_place_name,
            a.rdl,
            a.notes
        FROM assignments a
        JOIN technicians t ON t.id = a.technician_id
        JOIN items i ON i.id = a.item_id
        JOIN item_types it ON it.id = i.item_type_id
        WHERE a.closed=0
        ORDER BY t.name, it.name;
    """)

    selected_tech = st.selectbox(
        "Filtrar por técnico (opcional)",
        options=["(All)"] + (techs["name"].tolist() if len(techs) else []),
        key="friday_filter_tech"
    )

    if len(items_in_field) == 0:
        st.info("Nenhum assignment aberto.")
    else:
        df = items_in_field.copy()
        if selected_tech != "(All)":
            df = df[df["technician"] == selected_tech].copy()

        def days_since(x):
            if pd.isna(x) or not x:
                return None
            try:
                d = datetime.fromisoformat(str(x)).date()
                return (date.today() - d).days
            except Exception:
                return None

        df["ref_date"] = df["issued_date"].fillna(df["request_date"])
        df["days_since"] = df["ref_date"].apply(days_since)
        df["status"] = df["status"].apply(status_badge)

        show_cols = [
            "technician", "item_type", "serial_number", "asset_tag", "status",
            "request_date", "issued_date", "installed_date", "days_since",
            "location_place_name", "rdl", "notes"
        ]
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)

        st.download_button(
            "⬇️ Baixar CSV do Friday Check",
            data=df[show_cols].to_csv(index=False).encode("utf-8"),
            file_name=f"friday_check_{today_str()}.csv",
            mime="text/csv",
            key="dl_friday_check"
        )

# =========================
# TAB 1: Technicians
# =========================
with tabs[1]:
    st.subheader("👤 Technicians")

    with st.expander("➕ Add Technician", expanded=True):
        c1, c2, c3 = st.columns([1.2, 1.5, 0.8])
        with c1:
            tech_name = st.text_input("Name", placeholder="Ex: Wagner Veras", key="tech_add_name")
        with c2:
            tech_email = st.text_input("Email (optional)", placeholder="ex: name@company.com", key="tech_add_email")
        with c3:
            tech_active = st.selectbox(
                "Active",
                [1, 0],
                format_func=lambda x: "Yes" if x == 1 else "No",
                key="tech_add_active"
            )

        if st.button("Save Technician", type="primary", key="btn_save_tech"):
            if not tech_name.strip():
                st.error("Name é obrigatório.")
            else:
                try:
                    exec_sql(
                        "INSERT INTO technicians(name, email, active, created_at) VALUES (?, ?, ?, ?);",
                        (tech_name.strip(), tech_email.strip() or None, int(tech_active), datetime.utcnow().isoformat())
                    )
                    st.success("Technician cadastrado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Já existe um technician com esse nome.")

    st.divider()
    df = qdf("SELECT id, name, email, active, created_at FROM technicians ORDER BY name;")
    st.dataframe(df, use_container_width=True, hide_index=True)

    with st.expander("✏️ Update Technician"):
        if len(df) == 0:
            st.info("Cadastre um technician primeiro.")
        else:
            tech_pick = st.selectbox("Select Technician", df["name"].tolist(), key="tech_pick_update")
            row = df[df["name"] == tech_pick].iloc[0]

            new_email = st.text_input("Email", value=row["email"] if row["email"] else "", key="tech_update_email")
            new_active = st.selectbox(
                "Active",
                [1, 0],
                index=0 if int(row["active"]) == 1 else 1,
                format_func=lambda x: "Yes" if x == 1 else "No",
                key=f"tech_active_update_{int(row['id'])}"
            )
            if st.button("Update Technician", key="btn_update_tech"):
                exec_sql(
                    "UPDATE technicians SET email=?, active=? WHERE id=?;",
                    (new_email.strip() or None, int(new_active), int(row["id"]))
                )
                st.success("Atualizado.")
                st.rerun()

# =========================
# TAB 2: Item Types
# =========================
with tabs[2]:
    st.subheader("📦 Item Types (categorias)")

    with st.expander("➕ Add Item Type", expanded=True):
        type_name = st.text_input(
            "Type Name",
            placeholder='Ex: Carmanah Sign 30" / Printer / Booster / LCD',
            key="type_add_name"
        )
        if st.button("Save Item Type", type="primary", key="btn_save_type"):
            if not type_name.strip():
                st.error("Type name é obrigatório.")
            else:
                try:
                    exec_sql("INSERT INTO item_types(name) VALUES (?);", (type_name.strip(),))
                    st.success("Item Type cadastrado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Esse Item Type já existe.")

    st.divider()
    df = qdf("SELECT id, name FROM item_types ORDER BY name;")
    st.dataframe(df, use_container_width=True, hide_index=True)

# =========================
# TAB 3: Items (Scan SN)
# =========================
with tabs[3]:
    st.subheader("🧾 Items (Scan SN com câmera traseira)")

    types = qdf("SELECT id, name FROM item_types ORDER BY name;")
    if len(types) == 0:
        st.warning("Cadastre pelo menos 1 Item Type primeiro.")
        st.stop()

    # Session state do scan (igual ao PM scan)
    if "inv_scanner_buffer" not in st.session_state:
        st.session_state.inv_scanner_buffer = None
    if "inv_last_scan" not in st.session_state:
        st.session_state.inv_last_scan = ""
    if "inv_scan_on" not in st.session_state:
        st.session_state.inv_scan_on = False

    st.markdown("### 📷 Scan do Serial Number (barcode/QR)")
    st.info("Clique em **Start Scan** para abrir a câmera. Aponte para o código e ele será capturado automaticamente.")

    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("▶️ Start Scan", key="btn_inv_start_scan"):
            st.session_state.inv_scan_on = True
            st.session_state.inv_scanner_buffer = None  # Limpa buffer ao iniciar
            st.rerun()
    with c2:
        if st.button("⏹ Stop Scan", key="btn_inv_stop_scan"):
            st.session_state.inv_scan_on = False
            st.session_state.inv_scanner_buffer = None
            st.rerun()
    with c3:
        st.write("")

    # Scanner (igual ao PM scan)
    scanned_sn = None
    if st.session_state.inv_scan_on:
        st.markdown("### 📸 Scanner ativo - aponte para o código")
        scanned_sn = qrcode_scanner(key="inv_scan_sn_live")
        
        # Lógica igual ao PM scan
        if scanned_sn and scanned_sn != st.session_state.inv_scanner_buffer:
            st.session_state.inv_scanner_buffer = scanned_sn
            
            # Validação básica
            if len(scanned_sn) < 3:
                st.error("Código inválido. Por favor, tente novamente.")
                st.session_state.inv_scanner_buffer = None
            else:
                # Atualiza o último scan
                st.session_state.inv_last_scan = scanned_sn
                st.session_state.inv_scan_on = False
                
                # Feedback visual
                st.success(f"✅ SN capturado: {scanned_sn}")
                
                # Mostra preview do código capturado
                col1, col2 = st.columns(2)
                with col1:
                    st.info(f"**Serial Number:** {scanned_sn}")
                with col2:
                    st.code(f"Length: {len(scanned_sn)} characters")
                
                # Auto-advance com delay
                import time
                time.sleep(1.5)
                st.rerun()

    # Campo para digitação manual (fallback)
    st.markdown("### Ou digite manualmente:")
    
    # Determina o valor padrão para o campo de SN
    default_sn = st.session_state.inv_last_scan if st.session_state.inv_last_scan else ""
    
    with st.expander("➕ Add Item", expanded=True):
        c1, c2, c3 = st.columns([1.3, 1.3, 1.6])
        with c1:
            type_pick = st.selectbox("Item Type", types["name"].tolist(), key="inv_item_type")
        with c2:
            status = st.selectbox("Initial Status", ["AVAILABLE", "IN_FIELD", "INSTALLED", "LOST", "DAMAGED"], key="inv_item_status")
        with c3:
            asset_tag = st.text_input("Asset Tag (optional)", placeholder="Ex: ORC-001", key="inv_asset_tag")

        # Input do SN com o valor escaneado
        serial_number = st.text_input(
            "Serial Number (SN)", 
            value=default_sn, 
            key="inv_sn_input",
            placeholder="SN será preenchido automaticamente após o scan"
        )
        
        desc = st.text_input("Description (optional)", placeholder='Ex: "Carmanah 30", "Printer 4x6"', key="inv_desc")

        # Botão de salvar
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("💾 Save Item", type="primary", key="btn_save_item"):
                if not serial_number.strip():
                    st.error("Serial Number (SN) é obrigatório.")
                else:
                    type_id = int(types[types["name"] == type_pick]["id"].iloc[0])
                    try:
                        exec_sql("""
                            INSERT INTO items(serial_number, asset_tag, item_type_id, description, status, created_at)
                            VALUES (?, ?, ?, ?, ?, ?);
                        """, (
                            serial_number.strip(),
                            asset_tag.strip() or None,
                            type_id,
                            desc.strip() or None,
                            status,
                            datetime.utcnow().isoformat()
                        ))
                        st.success("✅ Item cadastrado com SN único.")
                        
                        # Limpa o scan após salvar com sucesso
                        st.session_state.inv_last_scan = ""
                        st.session_state.inv_scan_on = False
                        st.session_state.inv_scanner_buffer = None
                        
                        # Pequeno delay para mostrar mensagem de sucesso
                        import time
                        time.sleep(1.5)
                        st.rerun()
                        
                    except sqlite3.IntegrityError:
                        st.error("❌ SN já existe no sistema (duplicado).")
        
        with col2:
            if default_sn:
                st.info(f"Último SN escaneado: **{default_sn}**")

    # Instruções de uso
    with st.expander("📱 Dicas para usar o scanner no celular"):
        st.markdown("""
        ### Como usar o scanner:
        
        1. **Clique em "Start Scan"** para ativar a câmera
        2. **Permita o acesso à câmera** quando o navegador solicitar
        3. **Aponte para o código de barras/QR** do equipamento
        4. **Aguarde a leitura automática** - o scanner captura sozinho
        5. **O SN aparecerá no campo** e você poderá salvar o item
        
        ### Solução de problemas:
        
        - **Câmera não abre?** Verifique as permissões do navegador
        - **Não consegue ler?** Aumente a iluminação ou aproxime a câmera
        - **Código muito pequeno?** Aproxime mais a câmera
        - **Scanner não funciona?** Use a digitação manual como fallback
        
        ### Códigos válidos:
        - QR Codes
        - Códigos de barras (EAN, UPC, Code 128, etc)
        - Mínimo de 3 caracteres
        """)

    st.divider()
    
    # Lista de itens cadastrados
    st.markdown("### 📋 Itens Cadastrados")
    df = qdf("""
        SELECT
            i.id,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.description,
            i.status,
            i.created_at
        FROM items i
        JOIN item_types it ON it.id = i.item_type_id
        ORDER BY i.created_at DESC
        LIMIT 50;
    """)
    
    if len(df):
        df["status"] = df["status"].apply(status_badge)
        df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime('%d/%m/%Y %H:%M')
        
        # Mostra em formato de tabela
        st.dataframe(
            df[["item_type", "serial_number", "asset_tag", "status", "created_at"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "item_type": "Tipo",
                "serial_number": "Serial Number",
                "asset_tag": "Asset Tag",
                "status": "Status",
                "created_at": "Cadastrado em"
            }
        )
        
        # Total de itens
        total_items = qdf("SELECT COUNT(*) as total FROM items;").iloc[0,0]
        st.caption(f"Total de itens no sistema: **{total_items}**")
    else:
        st.info("Nenhum item cadastrado ainda.")

# =========================
# TAB 4: Assignments
# =========================
with tabs[4]:
    st.subheader("🔁 Assignments (Request → Issued → Installed → Returned)")

    techs = qdf("SELECT id, name FROM technicians WHERE active=1 ORDER BY name;")
    items = qdf("""
        SELECT
            i.id,
            it.name AS item_type,
            i.serial_number,
            COALESCE(i.asset_tag, '') AS asset_tag,
            COALESCE(i.description, '') AS description,
            i.status
        FROM items i
        JOIN item_types it ON it.id = i.item_type_id
        ORDER BY it.name, i.serial_number;
    """)

    open_assign = qdf("""
        SELECT
            a.id AS assignment_id,
            t.name AS technician,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.status,
            a.request_date,
            a.issued_date,
            a.installed_date,
            a.returned_date,
            a.location_place_name,
            a.rdl,
            a.notes
        FROM assignments a
        JOIN technicians t ON t.id = a.technician_id
        JOIN items i ON i.id = a.item_id
        JOIN item_types it ON it.id = i.item_type_id
        WHERE a.closed=0
        ORDER BY a.created_at DESC;
    """)

    st.markdown("### ➕ Create new Assignment (entregar/registrar item com técnico)")
    if len(techs) == 0 or len(items) == 0:
        st.warning("Cadastre technicians e items primeiro.")
    else:
        c1, c2, c3 = st.columns([1.2, 2.2, 1.1])
        with c1:
            tech_pick = st.selectbox("Technician", techs["name"].tolist(), key="assign_tech_pick")
        with c2:
            filter_status = st.selectbox("Mostrar itens", ["AVAILABLE (recommended)", "ALL"], key="assign_filter_items")
            items_filtered = items.copy()
            if filter_status.startswith("AVAILABLE"):
                items_filtered = items_filtered[items_filtered["status"] == "AVAILABLE"]

            def item_label(r):
                base = f"{r['item_type']} (SN: {r['serial_number']})"
                tag = f" | {r['asset_tag']}" if (r["asset_tag"] or "").strip() else ""
                desc = f" - {r['description']}" if (r["description"] or "").strip() else ""
                return base + tag + desc

            if len(items_filtered) == 0:
                st.error("Sem itens AVAILABLE. Ajuste status ou feche assignments antigos.")
                item_pick = None
            else:
                items_filtered = items_filtered.copy()
                items_filtered["label"] = items_filtered.apply(item_label, axis=1)
                item_pick = st.selectbox("Item", items_filtered["label"].tolist(), key="assign_item_pick")

        with c3:
            request_date = st.date_input("Request Date", value=date.today(), key="assign_req_date")

        issued_date = st.date_input("Issued Date", value=date.today(), key="assign_issued_date")
        location_place_name = st.text_input("Place Name (optional)", placeholder="Ex: Shoppers - Markham", key="assign_place")
        rdl = st.text_input("RDL (optional)", placeholder="Ex: RDL-1234", key="assign_rdl")
        notes = st.text_area("Notes (optional)", placeholder="Ex: Requested 3 signs + printer; install next week.", key="assign_notes")

        if st.button("Create Assignment", type="primary", disabled=(item_pick is None), key="btn_create_assignment"):
            tech_id = int(techs[techs["name"] == tech_pick]["id"].iloc[0])
            item_id = int(items_filtered[items_filtered["label"] == item_pick]["id"].iloc[0])

            exec_sql("""
                INSERT INTO assignments(
                    item_id, technician_id, request_date, issued_date,
                    location_place_name, rdl, notes, closed, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?);
            """, (
                item_id,
                tech_id,
                to_iso(request_date),
                to_iso(issued_date),
                location_place_name.strip() or None,
                rdl.strip() or None,
                notes.strip() or None,
                datetime.utcnow().isoformat()
            ))

            exec_sql("UPDATE items SET status='IN_FIELD' WHERE id=?;", (item_id,))
            st.success("Assignment criado. Item agora está IN_FIELD.")
            st.rerun()

    st.divider()
    st.markdown("### 📍 Open Assignments")

    if len(open_assign) == 0:
        st.info("Nenhum assignment aberto.")
    else:
        df = open_assign.copy()
        df["status"] = df["status"].apply(status_badge)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### ✏️ Update / Close Assignment")
        pick_id = st.selectbox("Select assignment_id", df["assignment_id"].tolist(), key="assign_pick_id")
        row = df[df["assignment_id"] == pick_id].iloc[0]

        installed_default = date.today()
        if isinstance(row["installed_date"], str) and row["installed_date"]:
            try:
                installed_default = datetime.fromisoformat(row["installed_date"]).date()
            except Exception:
                pass

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            new_installed = st.date_input("Installed Date (optional)", value=installed_default, key="assign_update_installed")
        with c2:
            mark_returned = st.checkbox("Returned (close, item AVAILABLE)", key="assign_mark_returned")
        with c3:
            mark_lost = st.checkbox("Mark LOST (close)", key="assign_mark_lost")
        with c4:
            mark_damaged = st.checkbox("Mark DAMAGED (close)", key="assign_mark_damaged")

        new_place = st.text_input("Place Name", value="" if pd.isna(row["location_place_name"]) else str(row["location_place_name"]), key="assign_update_place")
        new_rdl = st.text_input("RDL", value="" if pd.isna(row["rdl"]) else str(row["rdl"]), key="assign_update_rdl")
        new_notes = st.text_area("Notes", value="" if pd.isna(row["notes"]) else str(row["notes"]), key="assign_update_notes")

        if st.button("Save Update", key="btn_assign_save_update"):
            exec_sql("""
                UPDATE assignments
                SET installed_date=?, location_place_name=?, rdl=?, notes=?
                WHERE id=?;
            """, (to_iso(new_installed), new_place.strip() or None, new_rdl.strip() or None, new_notes.strip() or None, int(pick_id)))

            item_id = int(qdf("SELECT item_id FROM assignments WHERE id=?;", (int(pick_id),))["item_id"].iloc[0])

            if mark_lost:
                exec_sql("UPDATE items SET status='LOST' WHERE id=?;", (item_id,))
                exec_sql("UPDATE assignments SET closed=1, returned_date=? WHERE id=?;", (to_iso(date.today()), int(pick_id)))
                st.success("Item marcado como LOST e assignment fechado.")
            elif mark_damaged:
                exec_sql("UPDATE items SET status='DAMAGED' WHERE id=?;", (item_id,))
                exec_sql("UPDATE assignments SET closed=1, returned_date=? WHERE id=?;", (to_iso(date.today()), int(pick_id)))
                st.success("Item marcado como DAMAGED e assignment fechado.")
            elif mark_returned:
                exec_sql("UPDATE items SET status='AVAILABLE' WHERE id=?;", (item_id,))
                exec_sql("UPDATE assignments SET closed=1, returned_date=? WHERE id=?;", (to_iso(date.today()), int(pick_id)))
                st.success("Assignment fechado. Item voltou para AVAILABLE.")
            else:
                exec_sql("UPDATE items SET status='INSTALLED' WHERE id=?;", (item_id,))
                st.success("Atualizado. Item marcado como INSTALLED (assignment continua aberto).")

            st.rerun()

# =========================
# TAB 5: Export
# =========================
with tabs[5]:
    st.subheader("📤 Export / Reports")

    df_items = qdf("""
        SELECT
            i.id,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.description,
            i.status,
            i.created_at
        FROM items i
        JOIN item_types it ON it.id = i.item_type_id;
    """)
    df_assign = qdf("""
        SELECT
            a.id AS assignment_id,
            t.name AS technician,
            it.name AS item_type,
            i.serial_number,
            i.asset_tag,
            i.status,
            a.request_date,
            a.issued_date,
            a.installed_date,
            a.returned_date,
            a.location_place_name,
            a.rdl,
            a.notes,
            a.closed,
            a.created_at
        FROM assignments a
        JOIN technicians t ON t.id = a.technician_id
        JOIN items i ON i.id = a.item_id
        JOIN item_types it ON it.id = i.item_type_id;
    """)

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            "⬇️ Export Items CSV",
            data=df_items.to_csv(index=False).encode("utf-8"),
            file_name=f"items_{today_str()}.csv",
            mime="text/csv",
            key="dl_items"
        )
    with c2:
        st.download_button(
            "⬇️ Export Assignments CSV",
            data=df_assign.to_csv(index=False).encode("utf-8"),
            file_name=f"assignments_{today_str()}.csv",
            mime="text/csv",
            key="dl_assign"
        )

    df_show = df_assign.copy()
    if len(df_show):
        df_show["status"] = df_show["status"].apply(status_badge)
    st.dataframe(df_show.sort_values("created_at", ascending=False), use_container_width=True, hide_index=True)
