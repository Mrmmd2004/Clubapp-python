[app]
title = Clubapp
package.name = clubapp
package.domain = org.clubapp
source.dir = .
source.include_exts = py,png
source.exclude_dirs = libs,.github,bin,.buildozer
version = 1.0
requirements = python3,kivy==2.3.0,pyjnius,android
orientation = portrait
fullscreen = 0
icon.filename = %(source.dir)s/icon.png

android.permissions = INTERNET,ACCESS_NETWORK_STATE,WAKE_LOCK
android.archs = arm64-v8a
android.api = 33
android.minapi = 24
android.accept_sdk_license = True
android.add_libs_arm64_v8a = libs/arm64-v8a/*.so

[buildozer]
log_level = 2
warn_on_root = 1
