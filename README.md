# 一维水驱 Buckley–Leverett / Welge 分流服务

只做一件事：给定油水粘度、Swc、Sor 与 Corey 相对渗透率参数，在可动区间
`[Swc, 1-Sor]` 上算含水率分流函数 `f(Sw)`，从 `(Swc, 0)` 向 `f` 做 **Welge
切线**，切点饱和度 `Swf` 即激波前缘；激波后方按 `df/dSw` 铺稀疏波，返回整条
`ξ–Sw` 剖面。HTTP 对外，前端页面与后端同进程，切点计算只在后端。

## 数学定义

可动水饱和度：

```
s   = (Sw - Swc) / (1 - Sor - Swc),     0 <= s <= 1
krw = krw0 * s**nw
kro = kro0 * (1 - s)**no
f(Sw) = (krw/μw) / (krw/μw + kro/μo)
```

Welge 切点（在单位坐标 s 上是过原点的切线）满足

```
F'(s*) = F(s*) / s*
Swf = Swc + (1-Sor-Swc) * s*
ξ_f = f(Swf) / (Swf - Swc)          # 激波速度 = 切线斜率
```

求解器做三件硬校验，任何一条不过就返回 422，绝不拿中点饱和度凑斜坡：

1. `s*` 必须落在可动区间**开区间**内（落到端点即判失败）；
2. 切线在整条 `[0,1]` 上从下方支撑曲线（Rankine–Hugoniot / 熵条件）；
3. 斜率恒等式 `f(Swf)/(Swf-Swc) == df/dSw|Swf` 残差 < 1e-7。

剖面约定（连续注水、注入端 Sw = 1-Sor）：

```
ξ < df/dSw|(1-Sor)      Sw = 1-Sor     入口平台
稀疏波段                 ξ = df/dSw      Sw 连续（数值反演 df/dSw 单调支）
ξ = ξ_f                  Swf → Swc       竖直激波（不是斜坡）
ξ > ξ_f                  Sw = Swc        未扰动区
```

### 粘度比约定（重要）

服务内部使用标准定义 `r = μw/μo`。解析可验的趋势（等端点、nw=no=2 时
`s*=√(r/(1+r))`）：

- **驱替变有利** = 经典流度比 `M=(krw0·μo)/(kro0·μw)` 减小 = `μw/μo`
  增大（水更稠或油更稀）→ `Swf` **升高**、激波后稀疏波区间变短、前缘变钝、
  趋近活塞驱；
- 只加大 `Sor` → 末端 `1-Sor` 左移、可动区间变窄；
- `μw=μo、nw=no、krw0=kro0` 时，`f` 在中点严格对称（`f(0.5)=0.5`）。

> 注：若按字面把“水相对油的粘度比”理解成 μw/μo，则“该比值下降则 Swf
> 升高”与 Buckley–Leverett 数学相反；本服务以数学为准，并在测试
> `test_favorable_mobility_raises_swf` 中把方向钉死。

## 硬边界（违反即 422）

- `swc >= 0`，`sor >= 0`，且 `swc + sor < 1`（严格）；
- `μw > 0`，`μo > 0`；`nw > 0`，`no > 0`；
- `0 < krw0 <= 1`，`0 < kro0 <= 1`；
- 切线无内点解 / 切点落端点 / 不满足支撑条件 → 422 `tangent_failed`；
- 未知档名 → 404 `unknown_deck`。

## 运行

容器（基底 `python:3.12-slim`，单容器、只暴露 HTTP）：

```bash
docker build -t bl-welge .
docker run --rm -p 8080:8080 bl-welge
# 浏览器打开 http://localhost:8080/
```

本地（3.12）：

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 8080
```

## HTTP 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/decks` | 列出具名档（含粘度/Swc/Sor/端点/幂次） |
| GET | `/api/decks/{name}` | 读一档 |
| POST | `/api/decks/{name}` | 登记新档（重名 409） |
| PUT | `/api/decks/{name}` | 更新/建档 |
| POST | `/api/solve` | body 给 `name` 或 `params`（二选一），可带 `xi` 取样点 |
| GET | `/api/solve/{name}` | 点名一档直接出完整解（页面首屏用） |
| GET | `/` | 剖面台页面（同进程静态资源） |

`POST /api/solve` 示例（当次参数 + 调用方 ξ 取样点）：

```json
{
  "params": {"mu_w":1,"mu_o":2,"swc":0.2,"sor":0.2,
             "krw0":1,"kro0":1,"nw":2,"no":2},
  "xi": [0, 0.5, 2.0, 5.0]
}
```

响应含 `swf`、`f_swf`、`shock_speed`、`tangent_slope`、斜率/支撑残差、
可动区间上的 `f(Sw)` 曲线点、切线三点、带竖直激波重复点的剖面折线，以及
`samples`（Sw 在给定 ξ 上的取值）。

## 模块划分

```
app/core/relperm.py          Corey 相对渗透率
app/core/fractional_flow.py  f(Sw) 与解析 df/dSw
app/core/welge.py            切点搜索（二分 + 全局支撑校验）
app/core/profile.py          稀疏波反演表与 ξ 取样/剖面折线
app/models.py                Pydantic 硬边界校验
app/storage.py               具名档本地 JSON 存储
app/service.py               完整解装配
app/main.py                  FastAPI 路由与异常映射
app/static/                  纯展示前端（不计算切线）
tests/                       锁定全部不变量（35+ 项）
```

## 测试

```bash
python -m pytest
```

覆盖：切线斜率恒等式、末端 f=1、切点在开区间、有利方向 Swf 升高、
Sor 加大末端左移、中点当地导数冒充切线被剖面位置卡住、swc+sor 越界被拒、
粘度非正被拒、端点/无切线被拒、未知档名 404、激波竖直跳变等。
