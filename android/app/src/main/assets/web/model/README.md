# 安卓端 Live2D 模型（请自行放入）

本目录**不随仓库分发**角色模型，需要你自行放入一个 Live2D 模型：

```
android/app/src/main/assets/web/model/
├── your.model3.json
├── your.moc3
├── your.cdi3.json        （可选）
├── your.idle.motion3.json（可选）
└── textures/
    └── texture_00.png
```

然后在 `android/app/src/main/assets/web/app.js` 里把模型路径改成你的 `.model3.json` 文件名（搜索 `model3.json`）。
