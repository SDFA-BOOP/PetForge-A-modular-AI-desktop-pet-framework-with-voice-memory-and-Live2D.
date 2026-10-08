# voice — 语音接入接口

PetForge 通过**一个配置文件**接入任意 GPT-SoVITS 模型，不绑定角色、不改代码。

- 配置模板：`voice/model_config.example.json`
- 详细说明（一键训练 + 接入方法）：见仓库根目录 [README.md](../README.md#接入自己的音色模型)

## 最小接入（电脑端）

1. 复制模板并按你的路径填好：
   ```bat
   copy voice\model_config.example.json desktop\sovits_config.json
   ```
2. 启动配音服务：
   ```bat
   python desktop\phone_bridge.py --port 8765
   ```
   （桥接服务会调用本机 GPT-SoVITS 服务；也可直接运行 `voice/server/gpt_sovits_server.py`）

## 最小接入（安卓端）

把导出的 5 个 ONNX + `ref.wav` 放进：

```
android/app/src/main/assets/tts/
```

文件名与 `model_config.example.json` 的 `onnx` 段一致即可。

## 参数契约（App ↔ 模型）

| 模型文件 | 输入 | 输出 |
|----------|------|------|
| `ssl.onnx` | `ref_audio_16k` | `ssl_content` |
| `t2s_encoder` | `ref_seq, text_seq, ref_bert, text_bert, ssl_content` | `x, prompts` |
| `t2s_fs_decoder` | `x, prompts` | `logits, k_cache_0..N, v_cache_0..N, y_emb, x_example` |
| `t2s_s_decoder` | `iy, ik_cache_0..N, iv_cache_0..N, iy_emb, x_example` | `logits, k_cache_0..N, v_cache_0..N, y_emb` |
| `vits` | `text_seq, pred_semantic, ref_audio` | `audio` |
