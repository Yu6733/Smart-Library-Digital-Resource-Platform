# 智慧图书馆数字资源平台（源码说明）

## 一、运行环境准备
1. 安装 MongoDB（本项目在 7.0.16 上验证）并启动服务。
2. 安装 Python 依赖：`pip install -r requirements.txt`（只需 pymongo）。

## 二、怎么运行（任意工作目录都可以）
程序所有文件都按**脚本自身所在目录**定位（`os.path.dirname(os.path.abspath(__file__))`），
因此不要求先 `cd` 到源码目录，在别的盘/别的目录下用完整路径运行也可以：

```bat
python D:\你的路径\02-源码\01_main.py
```

数据文件（`books.txt` / `readers.txt` / `borrow_logs.txt`）、`config.json`、`gridfs_files\`、
导出的 `category_summary_export.json`、下载的电子书，全部在**源码目录**里读写，不会散落到当前工作目录。

## 三、数据库连接配置（不写死连接串）
连接串集中在 `config.json`：

| 字段 | 用途 |
|---|---|
| `uri` | 主程序使用的连接串（当前为副本集三节点 + authSource=library） |
| `db` | 数据库名，默认 `library` |
| `admin_uri` | 管理账号连接串（副本集运维脚本用） |
| `standalone_uri` | 单节点连接串（`init_repl.py` 初始化副本集用） |
| `shard_uri` | mongos 应用连接串（菜单 17 分片查询对比用，连不上会提示而不报错） |
| `shard_admin_uri` | mongos 管理连接串（`03-数据库与配置\verify_topology.py` 查分片清单用，需 clusterAdmin） |
| `repl_members` | 副本集成员地址列表（`init_repl.py` 用） |
| `repl_set` | 副本集名，默认 `rs0`（节点已用 `--replSet` 启动时以节点上报的为准） |

覆盖方式（优先级高于 config.json，全部为环境变量）：

```bat
set MONGODB_URI=mongodb://127.0.0.1:27017/
set MONGODB_DB=library
set MONGODB_SHARD_URI=mongodb://127.0.0.1:27217/library?authSource=library
set MONGODB_SHARD_ADMIN_URI=mongodb://127.0.0.1:27217/?authSource=admin
set MONGODB_STANDALONE_URI=mongodb://127.0.0.1:27017/?directConnection=true
set MONGODB_REPL_MEMBERS=127.0.0.1:27017,127.0.0.1:27018,127.0.0.1:27019
set MONGODB_REPL_SET=rs0
python 01_main.py
```

## 四、老师演示步骤（按顺序）
1. `python 01_main.py`
2. 输入 **`0`**：一键从源码目录读取三份 txt 并导入（books 50 / readers 30 / borrow_logs 3000）。
3. 输入 **`1`**：打印连接状态与七个集合文档数（与源文件行数一一对应）。
4. 输入 **`2`**，再输入 `计算机`：条件检索。
5. 输入 **`3`** / `9` / `15`：评分榜、畅销榜、学院借阅榜。
6. 输入 **`10`** 或 **`16`**：分类统计，并把结果写回 `category_summary` 集合。
7. 输入 **`11`**：读取 `gridfs_files\` 上传 6 个文件；**`13`** 查看清单（含 ISBN、类型、原始文件名、上传时间、分类）。
8. 输入 **`12`**，可填 ISBN `9787115428028` 或书名关键字 `深入理解计算机系统`：按 ISBN 或书名模糊匹配后下载到源码目录，并校验字节数与 SHA-256。
9. 输入 **`17`**：分片查询对比（需先启动分片集群与 mongos，见 `03-数据库与配置\启动与部署说明.md`）。它通过 mongos 执行 `explain`，打印定向查询与广播查询的执行阶段、命中分片、扫描文档数与服务器端平均耗时。
10. 输入 **`99`** 退出。

> 想验证「多端口 / 多节点」是否真的部署成功（副本集三节点、分片两片），
> 到 `03-数据库与配置` 目录执行 `python verify_topology.py`，它会打印 7 个端口的监听状态、
> 副本集一主两从与优先级、两个分片及借阅集合的分布比例；步骤说明见 `03-数据库与配置\启动与部署说明.md` 第 7 节。

## 五、只用单机 MongoDB 验证（不需要副本集）
如果只想快速跑通业务功能，可起一个单机 mongod（不带 --auth 最省事）：

```bat
mongod --port 27017 --dbpath .\data
set MONGODB_URI=mongodb://127.0.0.1:27017/
python 01_main.py
```

然后按上面第 2–9 步演示即可（副本集/分片相关的 `init_repl.py`、`test_failover.py`、
菜单 17 与 `admin_uri` 相关的运维脚本需要副本集环境，单机模式下跳过；已实测单机模式下
菜单 0 导入 50/30/3000、菜单 1 计数、菜单 2 检索均可正常工作）。

## 五之二、副本集初始化与故障转移演示
```bat
REM 1) 三个节点都用同一个 --replSet 与同一个 keyFile 启动，再执行初始化
python init_repl.py
REM 2) 先运行，脚本会写基线并提示你结束主节点进程；杀掉主节点后它会自动等到新主接管
python test_failover.py
```
`init_repl.py` 不写死地址：成员取自 `repl_members` 或 `MONGODB_REPL_MEMBERS`，
集合名取自节点启动参数里的 `--replSet`（再退到 `repl_set` / `MONGODB_REPL_SET`）；
对已初始化的集群重复执行只会打印当前角色，不会报错。

## 六、项目结构
- `01_main.py`：菜单式主交互界面
- `mongodb_connect.py`：连接封装（读 config.json / 环境变量，带脱敏打印）
- `data_initializer.py`：一键导入三份 txt，转换日期字段
- `file_manager.py`：GridFS 上传、按 ISBN 下载与字节/哈希校验
- `book_manager.py` / `reader_manager.py` / `borrow_manager.py`：图书、读者、借阅业务
- `stat_manager.py`：检索统计、$lookup 联合查询、$merge 物化视图、导出
- `audit_manager.py`：审计日志（写入固定集合 audit_logs）
- `init_repl.py` / `test_failover.py`：副本集初始化与故障转移演示脚本
- `books.txt` / `readers.txt` / `borrow_logs.txt`：原始数据
- `config.json`：连接配置
- `gridfs_files\`：6 个待上传的电子书与封面（含 files_manifest.txt 清单）
