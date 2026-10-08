# 构建与运行说明

## 1. 电脑端（desktop/）

依赖（见 `desktop/requirements.txt`）：

```
requests, edge-tts, pygame, SpeechRecognition, pyaudio, Pillow,
zhdate, live2d-py, pyopengltk, PyOpenGL
```

运行：

```bat
cd desktop
pip install -r requirements.txt
copy config.example.json config.json   # 填入你的 DeepSeek API Key
python main.py
```

- `phone_bridge.py` 是手机桥接服务，可单独运行：`python phone_bridge.py --port 8765`
- 桌宠设置页内也有「手机连接服务」一键启动/停止按钮。

## 2. 安卓端（android/）

- 使用 Android Studio 或 Gradle 打开 `android/` 工程。
- 需要 JDK 17、Android SDK（compileSdk 34）、NDK 26。
- 复制 `local.properties.example` 为 `local.properties` 并填 `sdk.dir`。

### 本地语音模型与动态库（需自行准备）

`android/app/src/main/jniLibs/` 与 `android/app/src/main/assets/tts/` 默认不随仓库分发，需要：

1. 用 `engine/` 的 Rust 工程编译出 `libgpt_sovits_demo_jni.so`（arm64-v8a / x86_64）。
2. 从 ONNX Runtime Maven AAR 解出 `libonnxruntime.so`。
3. 把 5 个 GPT-SoVITS ONNX（ssl / t2s_encoder / t2s_fs_decoder / t2s_s_decoder / vits）+ 参考音频放入 `assets/tts/`。

> **语音工具包（模型自备）**：仓库 Release 里的 [v0.1.0-voice-toolkit](https://github.com/SDFA-BOOP/PetForge-A-modular-AI-desktop-pet-framework-with-voice-memory-and-Live2D./releases/tag/v0.1.0-voice-toolkit) 提供：
> - nalyze/analyze_voice.py：解析参考音频音色（提取 SSL 内容特征）
> - server/gpt_sovits_server.py + sovits_config.example.json：接入你自己的 GPT-SoVITS 模型（电脑端配音服务）
> - xport/：把你训练的模型导出成 App 需要的 5 个 ONNX（KV-cache 格式）
>
> 本仓库**不附带**任何训练好的模型/音色，请用上述工具接入自备模型。

之后运行：

```bat
gradle assembleRelease
```

签名后安装即可。

## 3. 本地语音引擎（engine/gpt-sovits-android）

Rust 工程，依赖 `ort`（load-dynamic）+ `jpreprocess`（日语 G2P）。

### 前置

- Rust 工具链 + `cargo-ndk`
- Android NDK（`NDK_HOME`）
- ONNX Runtime Android 动态库（`libonnxruntime.so`，运行时 `load-dynamic` 加载，无需源码编译）

### 日语词典（jpreprocess-naist-jdic）

本仓库已内置一个 patch 版 `engine/vendor/jpreprocess-naist-jdic`：

- 若网络可访问 GitHub，构建时会自动下载 NAIST-jdic 词典。
- 若网络受限，先下载 `naist-jdic-jpreprocess.tar.gz`，构建时设置环境变量：

```bat
set NAIST_JDIC_TARBALL=C:\path\to\naist-jdic-jpreprocess.tar.gz
```

### 编译 JNI 动态库

```bash
cargo ndk -t arm64-v8a -p 24 -o jniLibs build --release --features jni --example gpt_sovits_demo_jni
```

输出 `libgpt_sovits_demo_jni.so`，放入安卓工程的 `app/src/main/jniLibs/arm64-v8a/`。

### 模型导出

引擎使用 KV-cache 版 GPT-SoVITS ONNX 导出格式，导出脚本见 `engine/gpt-sovits-android/scripts/GPT_SoVITS/export_onnx_v2.py`，
需要配合 GPT-SoVITS 原项目使用。
