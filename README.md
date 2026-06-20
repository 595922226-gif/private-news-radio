# 私人国际新闻电台 MVP

这是一个每天早上自动生成中文新闻音频的云端项目模板。

第一版目标：

- 每天东京时间 7:30 自动运行
- 抓取国际新闻 RSS 和公开信息
- 生成中文 Markdown 简报
- 生成适合朗读的中文口播稿
- 生成 MP3 音频
- 上传 `latest.mp3` / `latest.md`
- 发送邮件提醒和收听链接

## 你最终会得到什么

每天早上你会收到一封邮件，标题类似：

```text
2026年06月18日｜全球情报早餐
```

邮件里会有：

- 今日音频链接
- 今日文字简报
- 如果生成失败，会有错误原因

## 第一版需要准备的账号

1. GitHub 账号
2. OpenAI API Key
3. Cloudflare 账号和 R2 存储桶
4. 一个可发送邮件的邮箱 SMTP
5. 一个你在 iPhone 上能收到的邮箱

详细操作见：

- `docs/小白部署步骤.md`
- `docs/iPhone收听设置.md`

## 本地测试

如果你只是想先在电脑上测试一次：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_daily.py
```

没有配置 OpenAI Key 时，项目会生成一份演示简报和演示口播稿，但不会生成真实音频。

