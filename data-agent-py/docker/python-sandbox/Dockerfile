# Python 分析代码的沙箱镜像。
#
# 原项目用的是 continuumio/anaconda3（3GB+），这里换成精简版：
#   - 体积从 3GB 降到约 250MB，拉取快、占盘少
#   - 只装 prompt 里承诺给模型的库（pandas / numpy / scipy）
#
# 【为什么要把库预装进去】
#   沙箱执行时用了 --network none（断网），跑的时候没法 pip install，
#   所以依赖必须在这里装好。
#
# 换回完整版只需把环境变量指过去（不用改代码）：
#   DATA_AGENT_PYTHON_DOCKER_IMAGE=continuumio/anaconda3:latest

FROM python:3.12-slim

# 依赖说明：
#   pandas **必须锁在 2.x** —— prompt 模板里的示例代码用了
#     pd.to_numeric(df[col], errors='ignore')
#   这个参数在 pandas 3.0 被移除了，装上 3.x 的话模型照抄示例代码必然报
#     ValueError: invalid error value specified
#   （实测过一次：第一次执行失败，Supervisor 重试才成功。锁版本后一次就过。）
#   numpy / scipy：数据分析与统计计算常用，prompt 里承诺了 anaconda 默认库
RUN pip install --no-cache-dir "pandas<3" numpy scipy

# 代码通过只读卷挂进 /work，工作目录设在那儿
WORKDIR /work
