"""SQL 执行结果的模型。

对应 Java 的 SqlResultSet / DisplaySpec / SqlExecuteNode.SqlExecuteResult。
"""

from pydantic import BaseModel, Field

# 最多读多少行（照抄 Java 的 ResultSetBuilder）
MAX_ROWS = 1000


class SqlResultSet(BaseModel):
    """查询结果集。

    【注意数据类型】
      所有值都存成**字符串**。这是 Java 版的行为——
      因为前端表格展示不关心类型，统一成字符串省事。
    """

    column: list[str] = Field(default_factory=list, description="列名")
    data: list[dict[str, str]] = Field(default_factory=list, description="数据行")
    errorMsg: str | None = Field(default=None, description="错误信息")  # noqa: N815


class DisplaySpec(BaseModel):
    """给前端的展示配置。"""

    type: str = Field(default="table", description="展示类型：table/bar/line/pie")
    title: str = Field(default="", description="标题")
    x: str | None = Field(default=None, description="X 轴字段名")
    y: list[str] = Field(default_factory=list, description="Y 轴字段名列表")


class SqlExecuteResult(BaseModel):
    """执行节点的完整产出（结果集 + 展示配置）。"""

    resultSet: SqlResultSet = Field(default_factory=SqlResultSet)  # noqa: N815
    display: DisplaySpec = Field(default_factory=DisplaySpec)


def build_result_set(description, rows) -> SqlResultSet:
    """把 sqlite3 的查询结果转成 SqlResultSet。

    description 是 cursor.description（列信息），rows 是行数据。
    逻辑照抄 Java 的 ResultSetBuilder：
      1. 所有值转字符串，NULL 变空串
      2. 最多 1000 行
      3. 列名去掉反引号和双引号（SQLite 返回的列名可能带这些）
    """
    column_names = [str(d[0]) for d in (description or [])]
    cleaned_columns = [_clean_name(name) for name in column_names]

    data: list[dict[str, str]] = []
    for index, row in enumerate(rows):
        if index >= MAX_ROWS:
            break
        data.append(
            {
                cleaned: ("" if value is None else str(value))
                for cleaned, value in zip(cleaned_columns, row)
            }
        )

    return SqlResultSet(column=cleaned_columns, data=data)


def build_display_spec(result_set: SqlResultSet) -> DisplaySpec:
    """按结果集算展示配置。逻辑照抄 Java 的 buildDisplaySpec。"""
    if not result_set.column:
        return DisplaySpec(type="table", title="SQL已生成，等待外部执行")
    return DisplaySpec(
        type="table",
        title="SQL执行结果",
        x=result_set.column[0],
        y=result_set.column[1:],
    )


def _clean_name(name: str) -> str:
    return name.replace("`", "").replace('"', "")
