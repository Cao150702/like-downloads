# 理刻安装与更新

[安装与更新](https://cao150702.github.io/like-downloads/) · [问题反馈](https://github.com/Cao150702/like-downloads/issues/new/choose)

- 安装页会识别常见手机，顶部可手动选择苹果手机或安卓手机。在微信内打开时，页面提供切到浏览器的步骤和复制链接入口。
- 苹果手机先从 App Store 安装 TestFlight，再打开[外测邀请](https://testflight.apple.com/join/Ek6bg8ng)安装理刻。后续通过 TestFlight 更新。
- 安卓安装页与 App 内 OTA 均读取 `android/latest.json`。发布新版时提交清单及对应 APK，保留页面备用链接指向的安装包。
- 校内可在 WeLink 搜索曹天航、刘佳伟、季宇杰并私信。公开反馈请勿填写学号、密码和验证码。

## 校园公告

[App 读取地址](https://cao150702.github.io/like-downloads/notices/v1/feed.json) · [采集记录](https://github.com/Cao150702/like-downloads/actions/workflows/campus-notices.yml) · [网络测试](https://cao150702.github.io/like-downloads/notices/check.html)

GitHub Actions 每小时第 17 分读取校务、教务处教学运行、光电学院本科生和机械工程学院通知首页。Feed 按栏目保留原题、发布日期和官方原文链接。采集器只发布近 120 天内的条目，采集失败的栏目保留上次成功结果。首次发布需要四个栏目各成功一次。公告无变化时沿用现有文件。站点继续从 main 发布，公告工作流通过同仓 GITHUB_TOKEN 请求 Pages 重建。
