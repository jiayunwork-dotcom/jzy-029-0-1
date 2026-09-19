# 一维水驱 Buckley–Leverett / Welge 分流服务

只做一件事：给定油水粘度、`Swc`、`Sor`、Corey 端点与幂次，算出可动区间上的
含水率分流曲线 `f(Sw)`，从束缚水点 `(Swc, 0)` 向 `f` 作 **Welge 切线** 定出
激波前缘 `Swf`，激波后方按 `df/dSw` 铺**稀疏波**，给出整条 ξ = x/t 饱和度剖面。

- Python 3.12 + FastAPI，单进程同时吐 HTTP API 和前端静态页面
- 物性档持久化在本地 JSON 文件
- 前端只负责呈现，**切线/切点/剖面全部由后端计算**
- 不使用任何中心差分解激波，也不拿中点饱和度凑斜坡

## 物理模型

Corey 相对渗透率（`L = 1 - Sor - Swc`，`t = (Sw-Swc)/L`）：

```
krw = krw0 * t**nw
kro = kro0 * (1-t)**no
λw = krw/μw,  λo = kro/μo
f(Sw) = λw/(λw+λo)
```

Welge 切线（激波）：在归一化坐标上解切点 `t_f`

```
f(t_f)/t_f = f'(t_f)      ⇔      h(t) = t·f'(t) − f(t) = 0
```

硬校验（不满足直接拒绝求解，绝不凑斜坡）：

- 激波速度 `V = f(Swf)/(Swf − Swc)`，且等于切线斜率、等于切点处 `df/dSw`
- `Swf` 必须严格落在开区间 `(Swc, 1−Sor)`，退化为端点即失败
- `Sw ≤ Swc ⇒ f=0`；`Sw = 1−Sor ⇒ f=1`
- 稀疏波段逐点满足 `ξ = df/dSw`，连续单调，无跳跃
- 线性分流（`nw=no=1`）、幂次 `<1` 等无内部切线的情形一律拒绝

剖面：

```
ξ ≤ f'(1−Sor)        Sw = 1−Sor        注入端平台
f'(1−Sor) < ξ < V    ξ = f'(Sw) 反解    稀疏波（激波后方）
ξ = V                Sw: Swf → Swc      竖直激波
ξ > V                Sw = Swc           未见水原始带
```

### “流度比变有利 → Swf 升高、前缘变钝”的方向约定

按油藏工程标准，水油流度比 `M = (krw0/μw)/(kro0/μo)` 越小越有利（注入水
流度受抑制、驱替趋活塞式，如增粘水/聚合物驱）。**升高 `μw`** 使 `M` 下降、
`Swf` 升高、`V` 减小（前缘变钝）；反过来降低 `μw`（水更稀、`M` 增大）则
`Swf` 降低、前缘贴向 `Swc`。`tests/test_invariants.py` 锁住的就是这个方向。

> 说明：需求原文把“水相对油的粘度比下降”描述为流动性变有利。按上面的
> 标准定义，`μw/μo` 下降实际是更不利（水更容易窜流）。代码严格按
> `f=λw/(λw+λo)` 的物理定义实现，测试与页面提示按 `M` 减小 = 有利的
> 标准约定书写；若贵方内部约定相反，只需把页面上的滑杆方向反读，
> 求解结果本身不受影响。

## 启动

### 容器（推荐）

```bash
docker build -t bl-welge .
docker run --rm -p 8000:8000 bl-welge
# 浏览器打开 http://localhost:8000
```

只暴露 HTTP 8000 端口；物性档默认写在容器内 `/srv/data/profiles.json`。
需要持久化到宿主任意路径：

```bash
docker run --rm -p 8000:8000 -v $PWD/data:/srv/data bl-welge
```

### 本地

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## HTTP API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 剖面台页面 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/profiles` | 列出全部具名档（粘度、Swc、Sor、端点、幂次） |
| PUT | `/api/profiles/{name}` | 登记/更新一档（body 含 `name` + 8 个物性字段） |
| DELETE | `/api/profiles/{name}` | 删除一档 |
| POST | `/api/solve` | `{profile}` 或 `{params}` 求解；可带 `xi: [...]` 取样 |
| GET | `/api/solve/{name}?xi=0.1,0.5,1.2` | 直接对具名档求解 |

`/api/solve` 返回：`params`、`fractional_flow.{sw,f}`、`tangent`
（`swf/f_swf/shock_speed/slope/line`）、`profile`（稀疏波点、剖面折线，
激波为竖直段）、`samples`（请求的 ξ 点上的 Sw）。

错误一律带中文原因：缺项与类型错误、`Swc+Sor≥1`、粘度非正、端点越界、
幂次非正 → 400；切线无解 → 400；未知档名 → 404。

### 内置档

- `symmetric`：等粘度等幂次，f 在可动区间中点对称（页面默认）
- `standard`：油比水粘 4:1，不利流度比
- `favorable`：增粘水式有利流度比，Swf 高、前缘钝
- `heavy_oil`：高粘原油，极不利

## 模块划分

```
app/core/relperm.py     Corey 相对渗透率
app/core/fractional.py  f(Sw) 与解析 df/dSw
app/core/tangent.py     Welge 切点搜索（二分 + 端点极限校验）
app/core/solution.py    稀疏波反解、激波、ξ 取样、作图折线
app/models.py           物性硬校验
app/store.py            具名档本地文件存储
app/schemas.py          Pydantic 请求模型
app/main.py             FastAPI 路由与错误处理
app/static/             前端（只画不算）
tests/                  51 个测试
```

## 测试

```bash
pip install -r requirements-dev.txt
pytest
```

锁住的不变量：切线斜率 = `f(Swf)/(Swf−Swc)`；末端 f=1；切点在可动开区间；
流度比变有利则 Swf 升高、V 减小；Sor 加大则末端左移；用稀疏波内部当地导数
冒充激波速度会落在连续高饱和段（被位置卡住）；`Swc+Sor` 越界、粘度非正、
缺字段、切线无解、未知档名全部被拒。
