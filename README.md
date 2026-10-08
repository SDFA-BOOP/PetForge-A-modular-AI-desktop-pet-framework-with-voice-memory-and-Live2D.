# PetForge

**PetForge — An AI voice desktop-pet framework.**

一个可复用的 AI 桌宠框架：**套上任意角色**（Live2D / 立绘 / 精灵图），即可获得 AI 语音对话、长期记忆、动作系统与多端同步。

> **由来**：这个项目最初是为动画角色「小鸟游六花」（《中二病也要谈恋爱！》）打造的桌宠，
> 后来抽离成通用框架。仓库里保留的默认人设（`persona`）与示例配置仍是六花，可自行替换成任何角色。

> 本项目为「框架 + 示例」，训练好的语音模型、API Key、运行时数据等均未包含，需要自行准备。

## 特性

- 🎭 **角色无关**：角色是插件。内置 `register_model` 注册表，Live2D / 图片 / 精灵图 / 分层都能接入，换角色不改核心。
- 💬 **AI 对话**：OpenAI 兼容 API（如 DeepSeek），支持流式输出、人设提示词、情绪与动作。
- 🔊 **语音**：edge-tts 开箱即用；可接到本地 **GPT-SoVITS** 原声（含手机端本地推理）。
- 🧠 **记忆**：短期日志 + 长期摘要 + 每日整理，支持与手机同步。
- 🎬 **动作系统**：AI 可在回复末尾返回 `[动作:xxx]` / `[表情:xxx]`，用户可注册自定义动作。
- 📱 **多端**：电脑端（Python）+ 安卓端（Java/WebView）+ 本地语音引擎（Rust），局域网自动发现与记忆同步。

## 目录结构

```
PetForge/
├── desktop/                 # 电脑端桌宠（Python）
│   ├── main.py              # 入口
│   ├── phone_bridge.py      # 手机桥接服务（局域网 HTTP + UDP 自动发现 + 记忆同步）
│   ├── petforge/            # 核心包（框架内核）
│   ├── character/           # 角色素材目录（需自行放入，见其中 README）
│   ├── user_actions.py      # 用户自定义 AI 动作示例
│   └── config.example.json  # 配置示例（去掉密钥）
├── android/                 # 安卓端桌宠（Java + WebView 源码）
├── engine/                  # 本地 GPT-SoVITS 语音引擎（Rust）
├── voice/                   # 语音接入接口（模型配置模板 + 参数契约）
├── characters/              # 角色素材说明（素材本身不入库）
└── diary/                   # 日记软件（独立，后续单独整理）
```

> 说明：角色素材（Live2D / 立绘）**不随仓库分发**，请按 `characters/README.md` 放入各端目录。

## 技术栈

| 部分 | 语言 / 技术 |
|------|------|
| 电脑端 | Python 3、Tkinter、live2d-py、edge-tts、pygame |
| 安卓端 | Java、JavaScript、HTML/CSS、WebView、PIXI.js、Cubism SDK |
| 语音引擎 | Rust、ONNX Runtime、cargo-ndk、jpreprocess |

## 文档

- [使用说明书 / Live2D 参数绑定 / 自定义动作](docs/MANUAL.md)
- [构建与运行](docs/BUILD.md)

## 快速开始

- 电脑端：见 `docs/BUILD.md` 与 `desktop/requirements.txt`
- 安卓端：见 `docs/BUILD.md`
- 语音引擎：见 `docs/BUILD.md`（需先导出 GPT-SoVITS 模型）

> **语音工具包**：模型请自备——用 [https://github.com/SDFA-BOOP/PetForge-A-modular-AI-desktop-pet-framework-with-voice-memory-and-Live2D./releases/tag/v0.1.0-voice-toolkit] 里的「语音工具包」（音色解析 nalyze_voice.py + 配音服务 gpt_sovits_server.py + 模型导出 xport/）接入你自己的 GPT-SoVITS 模型。

## 给它换个角色

1. 准备角色资源（Live2D `.model3.json` 或立绘 PNG）。
2. 在角色渲染里通过 `register_model` 接入（参考 `desktop/petforge/character/`）。
3. 换掉人设提示词（`persona`）与 `config.json` 里的角色配置即可。

## 一键训练自己的音色模型

PetForge 本身**不训练模型**，训练交给 **GPT-SoVITS 官方整合包**（Windows 免安装，自带 WebUI）。

**1. 准备素材**

- 一段干净的单人语音：建议 **1~5 分钟**，无 BGM / 混响 / 他人声音（wav / mp3 均可）。
- 可选：对应文本（长音频需要切分时用）。

**2. 一键训练（GPT-SoVITS WebUI）**

1. 下载并解压 GPT-SoVITS 整合包，双击 `go-webui.bat` 启动 WebUI。
2. 打开「1-训练」页，用顶部的 **一键三连**：
   - **1A 训练集格式化**：填音频目录 / 清单，选说话人与语言，点「开启一键格式化」。
   - **1B 微调训练**：SoVITS / GPT 轮数用默认值即可，点「开启一键训练」。
3. 训练完成后会得到：
   - `SoVITS_weights/*.pth`
   - `GPT_weights/*.ckpt`
4. 到「1C 推理」页选刚训练的权重 + 一段参考音频试听，确认音色满意。

> 更细的参数说明见 GPT-SoVITS 官方文档 / 整合包内「一键三连」说明。

## 接入自己的音色模型

接入接口只有一个配置文件：**`voice/model_config.example.json`**（参数契约见 `voice/README.md`）。

### 电脑端（HTTP 服务）

1. 复制模板并填写你的模型路径：
   ```bat
   copy voice\model_config.example.json desktop\sovits_config.json
   ```
2. 启动服务：
   ```bat
   python desktop\phone_bridge.py --port 8765
   ```
3. 桌宠设置里「配音后端」选 `gpt_sovits`，地址填服务地址即可。服务提供 `GET /health` 与 `POST /tts`。

### 安卓端（本地 ONNX 推理）

App 需要 5 个 ONNX + 参考音频，放在：

```
android/app/src/main/assets/tts/
```

导出：用 Release「语音工具包」里的 `export/`（即 GPT-SoVITS 的 `export_onnx_v2.py`），把训练的 `.ckpt/.pth` 导出成 KV-cache 版 ONNX。

### 音色解析（可选）

工具包里的 `analyze/analyze_voice.py` 可把参考音频解析成 SSL 内容特征，用于检查 / 调试音色：

```bat
python analyze/analyze_voice.py --ref ref.wav --gpt-sovits E:/GPT-SoVITS --device cuda
```

## 许可说明

- 本项目源码按仓库根目录 `LICENSE` 许可（默认 MIT）。
- `android/.../assets/web/lib/` 中的第三方库（PIXI.js / Cubism SDK / OpenCV.js 等）遵循各自原始许可，请自行确认后商用。
- 角色素材不随仓库分发；若你自行添加素材，请确认其版权许可。
