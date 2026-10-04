"""数据库结构（Schema）对象。

对应 Java 版的 entity/dto/Schema.java。

【它在流程里的位置】
  table_relation 节点**产出**它（把召回的散碎表和列整理成一个结构化对象），
  feasibility / planner / sql_generator 三个节点**消费**它
  （把它渲染成文字，塞进各自的 prompt）。

【两种存在形式】
  1. 对象形式：反正各节点之间传的是一个 JSON 字符串，需要时 json.loads 回来
  2. 文字形式：build_scheme_prompt() 渲染成给人（和模型）看的格式
"""

from pydantic import BaseModel, Field


class DbColumnView(BaseModel):
    """表里的一列。

    注意字段名 `isPrimaryKey` 是驼峰——因为要和 Java 的
    @JsonProperty("isPrimaryKey") 保持一致，prompt 里也是这么引用的。
    """

    name: str = ""
    type: str = ""
    description: str = ""
    isPrimaryKey: bool = False  # noqa: N815 - 故意用驼峰，对齐 JSON 字段名


class DbTableView(BaseModel):
    """一张表的视图（表名 + 它的列）。"""

    name: str = ""
    columns: list[DbColumnView] = Field(default_factory=list)


class ForeignKeyTableView(BaseModel):
    """外键一端所属的表（只需要名字）。"""

    name: str = ""


class ForeignKeyColumnView(BaseModel):
    """外键一端的列。"""

    name: str = ""
    dbTable: ForeignKeyTableView = Field(default_factory=ForeignKeyTableView)  # noqa: N815


class DbForeignKeyView(BaseModel):
    """一条外键关系：源列 = 目标列。"""

    sourceColumn: ForeignKeyColumnView = Field(  # noqa: N815
        default_factory=ForeignKeyColumnView
    )
    targetColumn: ForeignKeyColumnView = Field(  # noqa: N815
        default_factory=ForeignKeyColumnView
    )

    def to_expression(self) -> str:
        """渲染成 "源表.源列 = 目标表.目标列" 这样的表达式。"""
        src = self.sourceColumn
        tgt = self.targetColumn
        if not src.name or not tgt.name or not src.dbTable.name or not tgt.dbTable.name:
            return ""
        return f"{src.dbTable.name}.{src.name} = {tgt.dbTable.name}.{tgt.name}"


class Schema(BaseModel):
    """一个数据库的结构快照。"""

    databaseId: str = ""  # noqa: N815
    dbTables: list[DbTableView] = Field(default_factory=list)  # noqa: N815
    dbForeignKeys: list[DbForeignKeyView] = Field(default_factory=list)  # noqa: N815
    enableExampleSampling: bool = False  # noqa: N815

    def build_scheme_prompt(self) -> str:
        """渲染成给大模型看的文字格式。

        输出长得像这样：
            【DB_ID】 california_schools
            # Table: frpm
            [
            (CDSCode: text
            , CDSCode, primaryKey, Examples: []),
            ...
            ]
            【Foreign keys】
            satscores.cdsc = schools.CDSCode

        格式是照抄 Java 的 Schema.buildSchemePrompt()——
        格式一变，模型的表现可能就跟着变，所以尽量别动。
        """
        parts: list[str] = [f"【DB_ID】 {self.databaseId}\n"]

        for table in self.dbTables:
            parts.append(self._build_table_prompt(table))

        keys = "\n".join(
            expr
            for expr in (fk.to_expression() for fk in self.dbForeignKeys)
            if expr
        )
        parts.append(f"【Foreign keys】\n{keys}")
        return "".join(parts)

    @staticmethod
    def _build_table_prompt(table: DbTableView) -> str:
        primary_keys = {c.name for c in table.columns if c.isPrimaryKey}
        builder = [f"# Table: {table.name}\n[\n"]
        for column in table.columns:
            line = f"({column.name}: {column.type}\n, {column.description}, "
            if column.name in primary_keys:
                line += "primaryKey, "
            # enableExampleSampling 关着，示例恒为空——跟 Java 默认行为一致
            line += "Examples: []),\n"
            builder.append(line)
        builder.append("]\n")
        return "".join(builder)
