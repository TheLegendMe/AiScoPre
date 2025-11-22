# AiScoPre

世界杯 AI 预测系统 · demo 版本

- 多服务 gRPC 架构（赛事、球队、用户、特征、模型、预测、HTTP 网关）
- 提供 `web/index.html` 单页应用，可视化模型概率 + 2026 世界杯赔率
- 包含 `scripts/scrape_wc2026.py`，演示如何在遵守网站规则的前提下抓取公开数据

## 快速启动

```bash
pip install -r requirements.txt
python3 scripts/gen_protos.sh
python3 scripts/start_all.py
```

浏览器访问 <http://localhost:8000/>，可以看到预测页面。

## Docker / Compose

```bash
docker-compose up --build
```

## 2026 世界杯数据（安全合规爬取）

1. 默认使用 `data/sample_wc2026_info.json` 中的演示数据，你可以直接在页面里看到赔率表。
2. 如果拿到明确授权的目标网站，可以运行：

   ```bash
   python3 scripts/scrape_wc2026.py \
     --source-url "https://example.com/world-cup-2026" \
     --allow-domain example.com
   ```

   - 脚本会先读取 robots.txt，若被禁止则直接退出；同时会在请求间 sleep（默认 1 秒）。  
   - 生成的 `data/latest_wc2026_info.json` 可通过设置 `WC2026_DATA_PATH` 环境变量让网关加载。
   - 未指定 `--source-url` 时脚本只解析 `data/sample_wc2026_source.html`，方便本地验证解析逻辑。

3. 更新数据后调用网关的 `POST /wc2026/reload` 即可热加载。

> **注意**：请确认目标站点允许抓取相应内容并遵守所有使用条款，否则不要运行真实抓取。

更多架构细节见 `docs/architecture.md`。
