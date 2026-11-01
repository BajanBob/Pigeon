// Adds the runtime permissions Pigeon needs to the generated Android manifest.
import fs from 'fs';
const p = 'android/app/src/main/AndroidManifest.xml';
let x = fs.readFileSync(p, 'utf8');
const perms = `
    <uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>
    <uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>
    <uses-permission android:name="android.permission.CAMERA"/>
    <uses-permission android:name="android.permission.RECORD_AUDIO"/>
    <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
    <uses-feature android:name="android.hardware.location.gps" android:required="false"/>
    <uses-feature android:name="android.hardware.camera" android:required="false"/>`;
if (!x.includes('ACCESS_FINE_LOCATION')) {
  x = x.replace(/(<manifest[^>]*>)/, `$1\n${perms}`);
  fs.writeFileSync(p, x);
  console.log('Patched AndroidManifest.xml with location/camera/mic permissions.');
} else {
  console.log('Android permissions already present.');
}
