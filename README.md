# 建模 Agent

一个本机运行的数学建模辅助原型。使用者填写自己的 DeepSeek API Key；模型根据任务决定是否调用论文检索或 Python 计算工具，然后解释结果。

> 该项目处于原型阶段，面向学习与研究。输出、文献、代码和比赛允许使用 AI 的要求，都需要人工核验。

## 功能

- 根据题目自主选择是否调用工具，最多调用 6 次；支持当前页面内最多 6 轮对话，新建对话或关闭页面后清空。
- 查询 Crossref 的论文元数据、作者、年份与 DOI。元数据不代表已经阅读全文，亦非通用网页搜索。
- 可选使用 DeepSeek Search API 搜索普通网页，搜索调用可能单独计费。
- 上传文本、CSV、XLSX、可提取文字的 PDF 和图片；文本在本地提取，图片发送至用户选择的视觉模型。图片功能依赖模型和接口实际支持。
- 可选在临时 Docker 容器运行 Python，读取上传的数据，生成可下载的 PNG 图表。
- 自行填写 OpenAI 兼容接口的基础地址、模型名和 API Key。密钥不会写入配置文件；模型及搜索分别按各自平台计费。

## 使用

需要 Python 3.10 或更高版本，以及一个有余额且支持工具调用的 OpenAI 兼容模型 API 账户。

```bash
git clone https://github.com/Yujoe19/math-model-agent.git
cd math-model-agent
pip install -r requirements.txt
python server.py
```

浏览器访问 <http://127.0.0.1:8789/>，填写 API 基础地址、模型名称、Key 和题目。默认使用 `https://api.deepseek.com` 的 `deepseek-flash`；其他 OpenAI 兼容服务可填其基础地址（如 `https://api.openai.com/v1`）。需在服务商处确认所选模型支持工具调用。上传图片时勾选“所选模型和接口支持图片”；是否支持由服务商和模型决定，不保证所有兼容接口都实现相同的图片格式。

每次最多 4 个文件、每个 3 MB、总计 8 MB。文本提取后发给模型；图片以 OpenAI 兼容的 `image_url` 数据格式发给模型。PDF 只提取文本，扫描页或图表需另存为图片上传；PDF 限 30 页，XLSX 每个工作表限 1000 行、100 列。CSV、TXT、JSON 和 XLSX 会复制到沙盒临时目录 `/tmp/data/`，仅用于本轮执行，容器结束后不保留。对话与选择的文件仅保留在浏览器页面内存；每轮会重新提交已选文件，可能增加模型费用，文件不会自动保存为项目。

勾选网页搜索时，使用 DeepSeek Search API：若模型地址就是 DeepSeek 可共用当前模型 Key，否则需额外填写 DeepSeek 搜索 Key。成功搜索可能产生服务商的独立费用。Crossref 论文搜索无需额外 Key；模型可能选择不调用启用的工具。

### 可选：启用 Python 计算

安装并启动支持 Linux 容器的 Docker Desktop 或 Docker Engine，预先下载 Python 镜像：

```bash
docker build -f Dockerfile.sandbox -t modeling-agent-sandbox:trial .
```

然后在页面勾选“允许运行 Python”。沙盒容器不开网络、不挂载主机文件或 Docker socket、以非 root 用户运行，并限制 CPU、内存、进程数、输出长度和运行时间。运行前不会自动下载镜像。镜像包含 NumPy、SciPy、pandas 和 Matplotlib，图表应输出到 `/tmp/output/*.png`。单次最多展示两张图，每张最大 450 KB。

Docker 隔离并不等于虚拟机级安全边界；不要用它运行不可信用户的任意代码来提供公共服务。超时会尝试停止并删除本次临时容器，若清理失败会提示手动检查 Docker。

## 使用与数据边界

- 服务仅监听 `127.0.0.1`，不是多人服务。不要转发端口或直接部署到公网。
- 密钥仅保留在浏览器和服务进程的运行时内存，不写入应用配置或请求日志。题目、文件提取文本及上传图片会发给配置的模型服务商；勾选搜索后检索词可能发送到 Crossref 或 DeepSeek。
- Python 执行默认关闭；当用户勾选后，模型可以在调用上限内自主运行代码。实际代码、输出及异常显示在页面中，仍需审阅。
- 模型可能出错、生成无效代码、遗漏约束，或把搜索到但不相关的文章当成参考。公开发表及参赛前请逐项核对。
- 支持 OpenAI 兼容 Chat Completions；不同平台对多模态及工具调用的实现可能不同，需单独核验。

## 验证

```bash
python -m unittest discover -s tests -v
```

测试包含模拟模型的工具选择与调用上限、多轮和图片消息格式、文件解析、密钥不回显和跨站请求拦截，以及实际 Docker 容器的网络隔离、绘图和超时清理。运行完整测试需要 Docker 和上述沙盒镜像。自动测试使用模拟模型，不会消耗 API 费用；不同服务商还需实际验证。

## 开发状态

这是一个本机试用原型，尚未实现永久项目保存、扫描 PDF OCR、所有图片平台适配、PDF 图文混排解析、文献全文阅读、SVG/PDF 图表、多用户隔离。欢迎先用公开练习题验证，再根据实际需求扩展。

## 许可证

MIT，见 [LICENSE](LICENSE)。
