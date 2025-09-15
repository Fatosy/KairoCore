from typing import Any, Dict, List, Optional, Tuple, Union
from common.errors import (
    MQSNT_PARAM_NONE_ERROR
)


class SqlTool:

    @staticmethod
    def generate_batch_insert_sql(table_name: str, param_dict_list: List[Dict]) -> Tuple[str, List[Dict]]:
        """ 生成批量insert语句 """
        if not param_dict_list:
            raise MQSNT_PARAM_NONE_ERROR

        # 获取列名列表
        columns = list(param_dict_list[0].keys())
        
        # 构建列名字符串，用逗号和空格分隔，并用反引号包裹（防止与关键字冲突，可选）
        columns_str = ", ".join([f"`{col}`" for col in columns])
        
        # 构建 :name 风格的占位符字符串
        # 例如，如果列是 ['name', 'age']，则占位符是 [':name', ':age']
        placeholders = [f":{col}" for col in columns]
        placeholders_str = ", ".join(placeholders)
        
        # 组装最终的 INSERT 语句
        insert_sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders_str});"
        
        return insert_sql, param_dict_list

    @staticmethod
    def generate_insert_sql(table_name: str, param_dict: Dict) -> Tuple[str, Dict]:
        """ 生成insert语句 """
        if not param_dict:
            raise MQSNT_PARAM_NONE_ERROR

        # 获取列名列表
        columns = list(param_dict.keys())
        
        # 构建列名字符串，用逗号和空格分隔，并用反引号包裹（防止与关键字冲突，可选）
        columns_str = ", ".join([f"`{col}`" for col in columns])
        
        # 构建 :name 风格的占位符字符串
        # 例如，如果列是 ['name', 'age']，则占位符是 [':name', ':age']
        placeholders = [f":{col}" for col in columns]
        placeholders_str = ", ".join(placeholders)
        
        # 组装最终的 INSERT 语句
        insert_sql = f"INSERT INTO `{table_name}` ({columns_str}) VALUES ({placeholders_str});"
        
        return insert_sql, param_dict
    
    @staticmethod
    def generate_update_sql(table_name: str, param_dict: Dict, where_dict: Dict) -> Tuple[str, Dict, Dict]:
        """ 生成update语句 """
        if not param_dict or not where_dict:
            raise MQSNT_PARAM_NONE_ERROR

        # --- 构建 SET 部分 ---
        set_columns = list(param_dict.keys())
        # 例如: "`column1` = :column1, `column2` = :column2"
        set_clause_parts = [f"`{col}` = :{col}" for col in set_columns]
        set_clause_str = ", ".join(set_clause_parts)

        # --- 构建 WHERE 部分 ---
        where_columns = list(where_dict.keys())
        # 例如: "`id` = :where_id, `status` = :where_status"
        # 为了避免与 SET 部分的参数名冲突，可以给 WHERE 的参数名加前缀
        where_clause_parts = [f"`{col}` = :where_{col}" for col in where_columns]
        where_clause_str = " AND ".join(where_clause_parts)
        new_where_dict = {f"where_{col}": where_dict[col] for col in where_columns}

        # 组装最终的 UPDATE 语句
        update_sql = f"UPDATE `{table_name}` SET {set_clause_str} WHERE {where_clause_str};"
        
        return update_sql, param_dict, new_where_dict

    @staticmethod
    def generate_hard_delete_sql(table_name: str, where_dict: Dict) -> Tuple[str, Dict]:
        """ 生成硬删除语句 """
        if not where_dict:
            raise MQSNT_PARAM_NONE_ERROR

        # --- 构建 WHERE 部分 ---
        where_columns = list(where_dict.keys())
        # 例如: "`id` = :where_id, `status` = :where_status"
        # 同样为 WHERE 的参数名加前缀以避免冲突
        where_clause_parts = [f"`{col}` = :where_{col}" for col in where_columns]
        where_clause_str = " AND ".join(where_clause_parts)
        new_where_dict = {f"where_{col}": where_dict[col] for col in where_columns}

        # 组装最终的 DELETE 语句
        delete_sql = f"DELETE FROM `{table_name}` WHERE {where_clause_str};"
        
        return delete_sql, new_where_dict
    
    @staticmethod
    def generate_soft_delete_sql(table_name: str, param_dict: Dict, where_dict: Dict) -> Tuple[str, Dict, Dict]:
        """ 生成软删除语句 """
        if not param_dict or not where_dict:
            raise MQSNT_PARAM_NONE_ERROR

        # --- 构建 SET 部分 ---
        set_columns = list(param_dict.keys())
        # 例如: "`column1` = :column1, `column2` = :column2"
        set_clause_parts = [f"`{col}` = :{col}" for col in set_columns]
        set_clause_str = ", ".join(set_clause_parts)

        # --- 构建 WHERE 部分 ---
        where_columns = list(where_dict.keys())
        # 例如: "`id` = :where_id, `status` = :where_status"
        # 为了避免与 SET 部分的参数名冲突，可以给 WHERE 的参数名加前缀
        where_clause_parts = [f"`{col}` = :where_{col}" for col in where_columns]
        where_clause_str = " AND ".join(where_clause_parts)
        new_where_dict = {f"where_{col}": where_dict[col] for col in where_columns}

        # 组装最终的 UPDATE 语句
        update_sql = f"UPDATE `{table_name}` SET {set_clause_str} WHERE {where_clause_str};"
        
        return update_sql, param_dict, new_where_dict