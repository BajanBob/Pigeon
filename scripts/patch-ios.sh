#!/usr/bin/env bash
# Adds the usage-description keys iOS requires before it will grant location,
# camera and microphone to the Pigeon WebView.
set -e
PLIST="ios/App/App/Info.plist"
PB=/usr/libexec/PlistBuddy

set_key () {
  local key="$1"; local val="$2"
  $PB -c "Add :$key string $val" "$PLIST" 2>/dev/null || $PB -c "Set :$key $val" "$PLIST"
}

set_key "NSLocationWhenInUseUsageDescription" "Pigeon uses your location to navigate and to share your position with people you choose."
set_key "NSLocationAlwaysAndWhenInUseUsageDescription" "Pigeon uses your location to keep sharing your live position while navigating."
set_key "NSCameraUsageDescription" "Pigeon uses the camera only for the optional live video feed you choose to share."
set_key "NSMicrophoneUsageDescription" "Pigeon uses the microphone only for the optional live audio feed you choose to share."

echo "Patched Info.plist with location/camera/microphone usage descriptions."
