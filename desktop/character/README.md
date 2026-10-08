# 电脑端角色素材（请自行放入）

本目录**不随仓库分发**角色素材（立绘 / Live2D 模型），需要你自行准备。

## 静态立绘

把 PNG 放到例如：

```
desktop/character/my_character.png
```

然后在 `desktop/config.json` 里设置：

```json
"character": { "type": "image", "image_path": "character/my_character.png" }
```

## Live2D 模型

把 `.model3.json` 及其依赖（`.moc3`、贴图、`.cdi3.json`、动作 json）放到：

```
desktop/character/live2d/T_runtime/
```

默认会读取 `character/live2d/T_runtime/192549kQzMyJqkgeAeZQyT.model3.json`；
也可在 `config.json` 里用 `character.live2d_model` 指定你自己的 `.model3.json`。

> 提示：Live2D native 无法读取含非 ASCII 的路径时，程序会自动复制到本地缓存目录再加载，无需手动处理。
