#!/usr/bin/env bash
# 构建毛概刷题 APK（不依赖 Gradle，直接用 aapt2 / javac / d8 / apksigner）
# 注意：aapt2 在 Windows 下不支持中文路径，所以统一在英文工作目录里编译。
set -e

SRC="/d/题库系统"
WORK="/d/AndroidBuild/proj_tiku"
SDK="/d/AndroidBuild/sdk"
BT="$SDK/build-tools/34.0.0"
PLATFORM="$SDK/platforms/android-34/android.jar"
JDK="/d/AndroidBuild/jdk-17.0.21.1+2"
export JAVA_HOME="D:\\AndroidBuild\\jdk-17.0.21.1+2"
export PATH="$JDK/bin:$PATH"

echo "[1/7] 准备英文工作目录 $WORK"
rm -rf "$WORK"
mkdir -p "$WORK/res/values" "$WORK/res/drawable" "$WORK/assets" "$WORK/gen" "$WORK/classes" "$WORK/dex"

echo "[2/7] 拷贝源码与网页资源"
cp "$SRC/android/AndroidManifest.xml" "$WORK/AndroidManifest.xml"
cp -r "$SRC/android/java" "$WORK/java"
cp "$SRC/android/res/values/strings.xml" "$WORK/res/values/strings.xml"
cp "$SRC/icon-192.png" "$WORK/res/drawable/ic_launcher.png"
cp "$SRC/index.html" "$WORK/assets/index.html"
cp "$SRC/manifest.webmanifest" "$WORK/assets/manifest.webmanifest"
cp "$SRC/sw.js" "$WORK/assets/sw.js"
cp "$SRC/icon-192.png" "$WORK/assets/icon-192.png"
cp "$SRC/icon-512.png" "$WORK/assets/icon-512.png"

echo "[3/7] 编译资源"
"$BT/aapt2.exe" compile --dir "$WORK/res" -o "$WORK/res.zip"

echo "[4/7] 链接资源包"
"$BT/aapt2.exe" link \
  -o "$WORK/base.apk" \
  -I "$PLATFORM" \
  --manifest "$WORK/AndroidManifest.xml" \
  -R "$WORK/res.zip" \
  -A "$WORK/assets" \
  --java "$WORK/gen" \
  --auto-add-overlay \
  --min-sdk-version 24 \
  --target-sdk-version 34

echo "[5/7] 编译 Java"
find "$WORK/java" "$WORK/gen" -name "*.java" | sed 's#^/d/#D:/#' > "$WORK/sources.txt"
"$JDK/bin/javac.exe" -source 8 -target 8 -encoding UTF-8 \
  -bootclasspath "$PLATFORM" -classpath "$PLATFORM" \
  -d "$WORK/classes" @"$WORK/sources.txt" > "$WORK/javac.log" 2>&1 || true
if [ ! -f "$WORK/classes/com/liu/tiku/MainActivity.class" ]; then
  echo "Java 编译失败："; iconv -f GBK -t UTF-8 "$WORK/javac.log" 2>/dev/null | head -20 || cat "$WORK/javac.log"
  exit 1
fi

echo "[6/7] 转 dex 并打进去"
find "$WORK/classes" -name "*.class" | sed 's#^/d/#D:/#' | tr '\n' ' ' > "$WORK/classlist.txt"
cmd //c "D:/AndroidBuild/sdk/build-tools/34.0.0/d8.bat --lib D:/AndroidBuild/sdk/platforms/android-34/android.jar --min-api 24 --output D:/AndroidBuild/proj_tiku/dex $(cat "$WORK/classlist.txt")"
ls -la "$WORK/dex/"

cp "$WORK/base.apk" "$WORK/unsigned.apk"
python - "$WORK/unsigned.apk" "$WORK/dex/classes.dex" <<'PY'
import sys, zipfile
apk, dex = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(apk, "a", zipfile.ZIP_DEFLATED) as z:
    z.write(dex, "classes.dex")
print("classes.dex 已加入 APK")
PY

echo "[7/7] 对齐 + 签名"
"$BT/zipalign.exe" -f 4 "$WORK/unsigned.apk" "$WORK/aligned.apk"

KS="$WORK/debug.keystore"
"$JDK/bin/keytool.exe" -genkeypair -keystore "$KS" -alias androiddebugkey \
  -storepass android -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
  -dname "CN=Android Debug,O=Android,C=US" >/dev/null 2>&1

cmd //c "D:\\AndroidBuild\\sdk\\build-tools\\34.0.0\\apksigner.bat sign --ks $(cygpath -w "$KS") --ks-pass pass:android --key-pass pass:android --v1-signing-enabled true --v2-signing-enabled true --out $(cygpath -w "$WORK\\signed.apk") $(cygpath -w "$WORK\\aligned.apk")"

cp "$WORK/signed.apk" "$SRC/题库系统.apk"
cp "$KS" "$SRC/android/debug.keystore"

echo ""
echo "=== 完成 ==="
ls -la "$SRC/题库系统.apk"
"$BT/aapt2.exe" dump badging "$WORK/signed.apk" 2>/dev/null | head -5 || true
