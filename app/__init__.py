"""Buckley-Leverett / Welge 分析服务。

模块划分：
- app.core.relperm    Corey 相对渗透率
- app.core.fractional 含水率分流函数 f(Sw) 及其解析导数
- app.core.tangent    从 (Swc, 0) 向分流曲线作 Welge 切线（激波前缘）
- app.core.solution   激波 + 稀疏波饱和度剖面与 ξ 取样
"""
