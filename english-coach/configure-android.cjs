const fs = require('node:fs');
const path = 'android/app/build.gradle';
let text = fs.readFileSync(path, 'utf8');
text = text.replace(/versionCode \d+/, 'versionCode 210').replace(/versionName "[^"]+"/, 'versionName "2.1"');
fs.writeFileSync(path, text);
// Stable development-only signing key. Never use this public key for store releases.
fs.writeFileSync('android/app/english-coach-debug.keystore', Buffer.from(fs.readFileSync('debug-signing-key.base64', 'utf8').trim(), 'base64'));
let gradle = fs.readFileSync(path, 'utf8');
if (!gradle.includes('signingConfigs.development')) {
gradle = gradle.replace('    buildTypes {', `    signingConfigs {
        development {
            storeFile file('english-coach-debug.keystore')
            storePassword 'android'
            keyAlias 'androiddebugkey'
            keyPassword 'android'
        }
    }
    buildTypes {`);
gradle = gradle.replace('    buildTypes {', '    buildTypes {\n        debug { signingConfig signingConfigs.development }');
}
fs.writeFileSync(path, gradle);
