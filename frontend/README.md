# AgentFlow 前端

Vue 3 + JavaScript + pnpm + Element Plus + Vue Router + Vite。

后端 `../backend` 未做任何改动。

---

## 一、启动

```bash
# 1 后端（另开一个终端，在 backend/ 目录下）
python -m uvicorn main:app --host 127.0.0.1 --port 8000

# 2 前端
cd frontend
pnpm install      # 已装过可跳过
pnpm dev          # http://localhost:5173
```

开发期前端统一请求 `/api/...`，由 `vite.config.js` 的 proxy 转发到
`http://127.0.0.1:8000`，**所以后端不需要开 CORS**。后端返回的 `/static/...`
资源地址也一并代理，因此上传后的图片/文件能直接显示。

生产部署时把 `/api` 与 `/static` 用 nginx 反代到后端即可，前端代码一行都不用改。

---

## 二、页面与接口对照

| 路由 | 页面 | 调用的后端接口 |
| --- | --- | --- |
| `/login` `/register` | 登录 / 注册 | `POST /auth/login`、`POST /auth/register` |
| `/` | 概览 | `GET /knowledge`、`GET /document/list` |
| `/knowledge` | 知识库列表（搜索 / 新建 / 编辑 / 删除） | `GET /knowledge`、`POST /knowledge`、`POST /knowledge/{id}/update`、`POST /knowledge/{id}/delete` |
| `/knowledge/:id` | 知识库详情 + 库内文档 | `GET /knowledge/{id}`、`GET /document/list` |
| `/documents` | 文档库（跨库筛选） | `GET /document/list`、`GET /knowledge` |
| `/retrieve` | 在线检索问答 | `GET /open/retrieve` |
| 上传抽屉（组件） | 上传 → 切分预览 → 入库 | `POST /document/upload`、`POST /document/split`、`POST /document/store` |
| 知识库图标上传 | — | `POST /upload/image` |

---

## 三、目录结构

```
src/
├── api/                    每个后端模块一个文件，只负责拼路径与参数
│   ├── request.js          fetch 封装：/api 前缀、Bearer token、错误归一化、401 钩子
│   ├── auth.js  knowledge.js  document.js  open.js
├── composables/
│   ├── useAuth.js          登录态单例（没装 pinia，用模块级 reactive + localStorage）
│   └── useDocumentCache.js 文档行跨页缓存 + **入库快照**（localStorage，详见第四节）
├── utils/
│   ├── format.js           字节 / 数字 / 时间 / 后缀等纯函数
│   ├── split.js            切分方式预设（下拉选项）、默认参数、展示工具
│   └── markdown.js         自研 Markdown → HTML 渲染器（先转义再解析，无第三方依赖）
├── components/
│   ├── AppIcon.vue             内联 SVG 图标（未装 @element-plus/icons-vue）
│   ├── StatCard.vue            概览统计卡
│   ├── MarkdownBlock.vue       Markdown 展示块（答案 / 召回片段 / 文档片段共用）
│   ├── KnowledgeFormDialog.vue 知识库新建/编辑弹窗
│   ├── SplitParamsDialog.vue   切分参数弹窗（分段方式下拉 + 长度 + 重叠度）
│   └── DocumentUploadDrawer.vue 上传→切分→入库三步抽屉
├── layouts/MainLayout.vue  侧栏 + 顶栏 + 内容区（<900px 侧栏收进抽屉）
├── router/index.js         路由表 + 登录守卫 + 标题
├── assets/main.css         设计令牌、Element Plus 主题覆盖、Markdown 排版、全局版式
└── views/                  8 个页面（含文档详情 views/DocumentDetailView.vue）
```

---

## 四、实现要点

- **登录态**：`localStorage` 存 token 与用户信息；任意请求收到 401 会清登录态并由路由守卫踢回登录页。
- **错误提示**：FastAPI 的 `detail`（含 422 的数组形式）统一归一化成一句中文，出错时**保留用户输入**。
- **登录/注册校验**与后端 schemas 严格对齐：用户名 3~64、密码 ≥6 且 UTF-8 ≤72 字节、邮箱可选。
- **知识库编辑**只提交改动过的字段，且不会传 `null`（否则后端 422）。
- **上传入库是三步三按钮**：`上传文件` → `切分`（先弹窗填参数，确认后才切）→ `确认入库`。
- **Markdown 渲染**：大模型答案、召回片段、文档片段正文统一走 `MarkdownBlock`。
  渲染器是自己写的，走「先整体转义 HTML、再解析 Markdown」的路线 ——
  文本来源是不可信的上传文档，这样结构上就没有注入面，也不用引 marked + DOMPurify。
  纯文本（没有 Markdown 语法）会自动退化成保留换行的纯文本，不会把作者敲的换行折叠掉。
- **入库快照与片段数还原**：详情页有三档数据来源，页面上会标出用的是哪一档（详见下）。
- **在线检索**因为单次 4.6~16 秒，做了阶段文案轮播 + 计时器，避免看起来像卡死。
- **响应式**：<900px 侧栏转抽屉，<760px 文档表格转卡片列表，触摸目标 ≥40px。
- **无障碍**：语义标签、可见焦点环、`prefers-reduced-motion` 下关闭动画。

### 4.1 文档详情页的片段从哪来（为什么不是简单调一个接口）

后端没有「按文档查已入库片段」的接口，`documents_chunks` 表没暴露；**入库时用的切分参数也没有存库**。
如果详情页拿默认 `chunk_size=512` 去 `/document/split` 重新切一遍，切出来的块数会跟入库时不一样
（同一份 5561 字的文档：512 → 14 块、256 → 28 块、128 → 112 块），
于是出现过「列表说 4 块、详情页只有 1 块」的自相矛盾。

现在按三级取，并在页面上用标签如实标注来源：

| 档位 | 来源 | 标签 |
| --- | --- | --- |
| ① | 入库那一刻写下的 localStorage 快照，逐块与库里一致 | 入库快照 |
| ② | 按库里的 `chunk_count` **自适应反推** `chunk_size` 再切，块数已对齐 | 已还原入库参数 |
| ③ | 反推没命中，给出最接近的一次并说明 | 未能精确还原 |

②的自适应算法：先用 `字符数 / 块数 × 0.75` 估一个起始档位，之后每试一次就按
`下一个 ≈ 当前 × 实测块数 / 目标块数` 跳一步。实测 12 个档位全部命中，平均 2.67 次、最坏 5 次
（纯逐个试要 6 次以上）。

> 后端如果补上「按文档查片段」的接口（或在 `documents` 表存下入库参数），这一页可以简化成一次查询。
> 当前实现是在现有接口下的可行方案，不是理想方案。

---

## 五、验证情况

- `pnpm build` 通过（各页面按路由分块，MarkdownBlock 独立成 5.5 kB 的 chunk）。
- 联调冒烟 **68 项全绿**：走真实 vite 代理打真实后端，覆盖注册/登录/401、知识库 CRUD 与 409/404/422
  分支、上传（含 .exe 与空文件被拒）、两处路径穿越被挡、切分、真实向量化入库、重复入库跳过、
  文档列表分页与关键字过滤、真实 LLM 检索、静态资源取回、外键 RESTRICT 保护。
- Markdown 渲染器单元测试 **63 项全绿**：注入转义（`<script>` / `onerror` / `javascript:` / 外链 SVG）、
  块级与行内语法、表格对齐、不重复转义、嵌套占位符、纯文本判定。
- 入库快照层单元测试 **25 项全绿**：一致性校验（文档重新入库后旧快照失效）、
  刷新持久化、24 条淘汰策略、坏数据与 localStorage 禁用时的降级。
- 片段数反推算法用**真实后端**验证：12 个 `chunk_size` 档位全部命中正确的块数，平均 2.67 次、最坏 5 次。
- 测试数据（用户 / 知识库 / 文档 / 磁盘文件 / Chroma 集合）已全部清理，`backend/data` 与 MySQL 回到测试前状态。

> 沙箱限制说明：在 WorkBuddy 沙箱内启动的后端进程无法写 SQLite，`/document/store`、`/open/retrieve`
> 会抛 `chromadb.errors.InternalError: disk I/O error`。这是运行环境限制，不是代码问题 ——
> 在正常终端里启动后端即可，无需任何改动。

---

## 六、建议后端修改的项

按优先级排列。**当前前端已按现有行为适配，不改也能正常用**。

### A. 影响功能完整性

1. **`GET /knowledge` 返回裸数组，没有 `total`**
   前端列表页只能做「上一页 / 下一页」，无法显示总页数（`/document/list` 已经是 `{total,page,limit,items}`）。
   建议统一成同样的分页结构。

2. **`/document/list` 不返回文件访问地址**
   `documents` 表没有路径列，落盘在 `data/documents/<YYMMDD>/<uuid>`，前端拼不出日期目录，
   所以**文档列表无法提供下载/预览**。建议在 items 里补 `url`（或给表加 `path` 列）。

3. **没有删除文档的接口**
   只能入库不能删除，前端也不敢做删除按钮 —— 删了 MySQL 行 Chroma 向量还在。
   建议加 `POST /document/{id}/delete`：按 `mysql_document_id` 或 `filename_uuid` 删向量，
   再删 `documents_chunks` / `documents`，最后回写 `knowledge_bases.document_num` / `str_num`。

4. **没有「取当前用户信息」的接口**
   前端刷新页面只能从 localStorage 恢复用户信息，token 失效要等下一次请求才发现。
   可以加 `GET /auth/me`（直接复用 `get_current_user`）。

5. **没有「按文档查已入库片段」的接口**
   `documents_chunks` 表存着正文，但没有接口暴露；`documents` 表也没存入库时用的
   `separator / chunk_size / chunk_overlap`。结果是文档详情页拿不到「库里那份真片段」，
   只能按 `chunk_count` 反推参数重切一遍（见第四节 4.1），会出现块数相同但正文有字符级差异的情况。
   建议加 `GET /document/{id}/chunks`，或在 `documents` 表补三列参数 —— 加完这一页能简化成一次查询。

### B. 安全 / 健壮性

6. **`POST /document/upload`、`POST /document/split` 没有鉴权**
   任何人（不需要登录）都能上传文件写盘；只要知道 `filename_uuid` 就能读回别人的文件内容。
   建议加 `Depends(get_current_user)`（前端请求本来就已经带 token，加上不用改前端）。

7. **`GET /open/retrieve` 不鉴权，也不校验知识库归属**
   知道 `knowledge_id` 就能检索任何人的知识库，并消耗你的 DashScope 额度。
   如果「开放」是有意设计，建议至少加限流或一个简单的 API Key；否则应加归属校验。

8. **`GET /knowledge` 的 `limit` 没有上限**
   `limit=99999` 会一次拉全表（`/document/list` 有 `le=100`，这里没有）。
   另外 `keyword` 没有像 `DocumentListQuery` 那样把空串归一化成 `None`，传 `keyword=` 会拼出 `LIKE '%%'`。

9. **`JWT_SECRET_KEY` 硬编码在 `app/router/auth.py`**，且 `jwt.encode` 没有 `exp`
   —— token 永不过期，`get_current_user` 里的 `ExpiredSignatureError` 分支永远不会触发。
   建议密钥移到环境变量，并加过期时间（前端已能处理 401，加上不用改前端）。

10. **`main.py` 没有 `CORSMiddleware`**
   现在靠 vite proxy 绕过。如果以后前端单独部署到别的域名/端口，会直接跨域失败。

### C. 性能

11. **`/open/retrieve` 每次请求都 new 一个 `MainRAG`**
    每次都要把整个集合拉出来重建 BM25，实测单次 4.6~16 秒。
    建议按 `(collection_name, settings)` 在进程内缓存实例。

12. **DashScope 偶发失败会让接口返回 500（Starlette 纯文本 `Internal Server Error`）**
    前端只能显示这句英文。建议包一层 `try/except` 转成 502/503 + 中文 `detail`。

13. **`find_document_file()` 每次遍历 `data/documents` 下所有日期目录**
    文档多了会变慢（`/split`、`/store` 每个文件都要扫一遍）。

### D. 一致性（可选）

14. `SplitIn` 还留在 `router/document.py` 里，其他请求体都已移到 `app/schemas/`。
15. 知识库的修改 / 删除用的是 `POST /{id}/update`、`POST /{id}/delete`，
    与 RESTful 习惯（`PUT/PATCH`、`DELETE`）不一致 —— 前端已适配，改不改都行。
