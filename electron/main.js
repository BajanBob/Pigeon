// Pigeon — Windows desktop shell (Electron)
// Loads the same www/index.html used by the Android/iOS builds and the web app.
// Grants geolocation, camera and microphone to the page so navigation, the
// compass and optional live video/audio sharing work exactly as on phone.

const { app, BrowserWindow, session, systemPreferences } = require('electron');
const path = require('path');

function createWindow() {
  const win = new BrowserWindow({
    width: 430,
    height: 880,
    minWidth: 360,
    minHeight: 560,
    backgroundColor: '#0a0f14',
    title: 'Pigeon',
    icon: path.join(__dirname, '..', 'resources', 'icon.png'),
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  // Grant the page the device permissions it needs (location, camera, mic).
  const ses = win.webContents.session;
  ses.setPermissionRequestHandler((wc, permission, callback) => {
    const ok = ['media', 'geolocation', 'audioCapture', 'videoCapture', 'clipboard-read', 'clipboard-sanitized-write'];
    callback(ok.includes(permission));
  });
  ses.setPermissionCheckHandler(() => true);

  // On Windows, make sure the OS-level location/camera/mic are available.
  try {
    if (process.platform === 'win32') {
      systemPreferences.askForMediaAccess && systemPreferences.askForMediaAccess('camera');
      systemPreferences.askForMediaAccess && systemPreferences.askForMediaAccess('microphone');
    }
  } catch (e) { /* non-fatal */ }

  win.setMenuBarVisibility(false);
  win.loadFile(path.join(__dirname, '..', 'www', 'index.html'));
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
