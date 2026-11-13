const fs = require('node:fs');
const path = 'android/app/build.gradle';
let text = fs.readFileSync(path, 'utf8');
text = text.replace(/versionCode \d+/, 'versionCode 200').replace(/versionName "[^"]+"/, 'versionName "2.0"');
fs.writeFileSync(path, text);
