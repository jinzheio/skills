# Microsoft Clarity 配置

Microsoft Clarity 提供会话录制、热图、rage click 和 UX 摩擦检测。

## 注入

```tsx
import Script from 'next/script';

export function MicrosoftClarity() {
  return (
    <Script
      id="microsoft-clarity"
      strategy="afterInteractive"
    >
      {`
        (function(c,l,a,r,i,t,y){
          c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
          t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
          y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
        })(window, document, "clarity", "script", "YOUR_PROJECT_ID");
      `}
    </Script>
  );
}
```

在 root layout 中 mount：

```tsx
<MicrosoftClarity />
```

没有环境变量时，所有访问者都能看到内容，注入不阻塞。不想加载时移除组件或加 feature flag。

## 项目 ID 来源

优先读取：

1. `SITE_INTEGRATIONS_CONFIG` JSON 中对应域名的 `clarity.project_id`
2. 当前进程 env 的 `CLARITY_ID`（或框架前缀的 `NEXT_PUBLIC_CLARITY_ID`）
3. 团队约定项目缓存

以上都没有时，跳过 Clarity。

## 与 Umami 的互补关系

| 维度 | Umami | Clarity |
|---|---|---|
| 访问量、来源、事件 | ✅ 强 | 弱 |
| 用户行为录像 | 无 | ✅ 核心功能 |
| 热图 / 点击分布 | 无 | ✅ |
| Rage click / 失败交互 | 无 | ✅ |
| 漏斗分析 | ✅ goals + funnels | 无 |

两者重叠在页面访问，但回答不同问题：Umami 回答 "多少人做了什么"，Clarity 回答 "具体怎么操作的、哪里点不动、哪里让人暴躁"。
