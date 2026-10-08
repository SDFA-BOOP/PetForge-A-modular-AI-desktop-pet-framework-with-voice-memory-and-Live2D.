# PetForge

**PetForge — An AI voice desktop-pet framework.**

一个可复用的 AI 桌宠框架：**套上任意角色**（Live2D / 立绘 / 精灵图），即可获得 AI 语音对话、长期记忆、动作系统与多端同步。

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
│   ├── rikka/               # 核心包（可整体重命名）
│   ├── character/           # 角色素材目录（需自行放入，见其中 README）
│   ├── user_actions.py      # 用户自定义 AI 动作示例
│   └── config.example.json  # 配置示例（去掉密钥）
├── android/                 # 安卓端桌宠（Java + WebView 源码）
├── engine/                  # 本地 GPT-SoVITS 语音引擎（Rust）
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
2. 在角色渲染里通过 `register_model` 接入（参考 `desktop/rikka/character/`）。
3. 换掉人设提示词（`persona`）与 `config.json` 里的角色配置即可。

## 许可说明

- 本项目源码按仓库根目录 `LICENSE` 许可（默认 MIT）。
- `android/.../assets/web/lib/` 中的第三方库（PIXI.js / Cubism SDK / OpenCV.js 等）遵循各自原始许可，请自行确认后商用。
- 角色素材不随仓库分发；若你自行添加素材，请确认其版权许可。
