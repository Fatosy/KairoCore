from typing import Dict, List, Tuple, Any
from ..common.errors import (
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
    def generate_batch_update_sql(table_name: str, param_dict_list: List[Dict], where_keys: List[str]) -> Tuple[str, Dict]:
        """ 生成批量update语句 """
        if not param_dict_list or not where_keys:
            raise MQSNT_PARAM_NONE_ERROR
        
        # 验证所有参数字典都包含 WHERE 键
        for i, param_dict in enumerate(param_dict_list):
            for key in where_keys:
                if key not in param_dict:
                    raise MQSNT_PARAM_NONE_ERROR.msg_format(f"参数字典 {i} 中缺少 WHERE 键 '{key}'")
        
        # --- 构建 SET 部分 ---
        # 从参数字典中排除 WHERE 键来构建 SET 列
        sample_param_dict = param_dict_list[0]
        set_columns = [col for col in sample_param_dict.keys() if col not in where_keys]
        
        if not set_columns:
            raise MQSNT_PARAM_NONE_ERROR.msg_format("没有可用于更新的字段")
        
        # --- 构建 WHERE 部分 ---
        # 构建完整的批量 SQL 和参数字典
        sql_parts = []
        all_params = {}
        
        for i, param_dict in enumerate(param_dict_list):
            # 构建 SET 子句
            set_clause_parts = []
            
            for col in set_columns:
                placeholder = f"{col}_{i}"
                set_clause_parts.append(f"`{col}` = :{placeholder}")
                all_params[placeholder] = param_dict[col]
            
            set_clause_str = ", ".join(set_clause_parts)
            
            # 构建 WHERE 子句
            where_clause_parts = []
            for col in where_keys:
                placeholder = f"where_{col}_{i}"
                where_clause_parts.append(f"`{col}` = :{placeholder}")
                all_params[placeholder] = param_dict[col]
            
            where_clause_str = " AND ".join(where_clause_parts)
            
            # 组装单条 UPDATE 语句
            update_sql = f"UPDATE `{table_name}` SET {set_clause_str} WHERE {where_clause_str};"
            sql_parts.append(update_sql)
        
        # 组合所有 SQL 语句
        final_sql = " ".join(sql_parts)
        
        return final_sql, all_params

    @staticmethod
    def generate_hard_delete_sql(table_name: str, where_dict: Dict, where_ops: Dict) -> Tuple[str, Dict]:
        """ 生成硬删除语句 """
        if not where_dict:
            raise MQSNT_PARAM_NONE_ERROR

        # --- 构建 WHERE 部分 ---
        where_columns = list(where_dict.keys())
        # 例如: "`id` = :where_id, `status` = :where_status"
        # 同样为 WHERE 的参数名加前缀以避免冲突
        where_clause_parts = [f"`{col}` {where_ops[col]} :where_{col}" for col in where_columns]
        where_clause_str = " AND ".join(where_clause_parts)
        new_where_dict = {f"where_{col}": where_dict[col] for col in where_columns}

        # 组装最终的 DELETE 语句
        delete_sql = f"DELETE FROM `{table_name}` WHERE {where_clause_str};"
        
        return delete_sql, new_where_dict
    
    @staticmethod
    def generate_soft_delete_sql(table_name: str, param_dict: Dict, where_dict: Dict, where_ops: Dict) -> Tuple[str, Dict]:
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
        where_clause_parts = [f"`{col}` {where_ops[col]} :where_{col}" for col in where_columns]
        where_clause_str = " AND ".join(where_clause_parts)
        new_where_dict = {f"where_{col}": where_dict[col] for col in where_columns}

        # 组装最终的 UPDATE 语句
        update_sql = f"UPDATE `{table_name}` SET {set_clause_str} WHERE {where_clause_str};"
        update_params = {**param_dict, **new_where_dict}
        
        return update_sql, update_params
    
    @staticmethod
    def query_list_params_translate(query_params: Dict, where_sqls: List[str], where_params: Dict, like_keys: List[str], in_keys: List[str], daterange_keys: List[str]):
        """ 查询列表参数转换 """
        for query_key in query_params.keys():
            if query_params[query_key] is not None and query_params[query_key] != [] and query_params[query_key] != "":
                if query_key in like_keys:
                    where_sqls.append(f' `{query_key}` like :{query_key} ')
                    where_params[query_key] = f'%{query_params[query_key]}%'
                elif query_key in daterange_keys:
                    where_sqls.append(f' ( `{query_key}` between :{query_key}_start and :{query_key}_end )') 
                    where_params[query_key + '_start'] = query_params[query_key][0]
                    where_params[query_key + '_end'] = query_params[query_key][1]
                elif query_key in in_keys:
                    where_sqls.append(f' `{query_key}` IN :{query_key} ')
                    where_params.update({query_key: query_params[query_key]})
                else:
                    where_sqls.append(f' `{query_key}` = :{query_key} ')
                    where_params.update({query_key: query_params[query_key]})