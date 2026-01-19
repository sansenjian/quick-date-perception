# quick-date-perception

> 轻量级日期感知插件，为麦麦提供时间、日期、节假日、农历、节气等环境感知能力

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/sansenjian/quick-date-perception)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![MaiBot](https://img.shields.io/badge/MaiBot-%E2%89%A50.7.0-orange.svg)](https://github.com/Maim-with-u/MaiBot)
[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Author](https://img.shields.io/badge/author-sansenjian-purple.svg)](https://github.com/sansenjian)

## ✨ 特性

- 🕐 **时区感知** - 支持配置时区，准确获取当前时间
- 📅 **日期识别** - 自动识别星期几和时间段（上午/中午/下午/晚上/深夜）
- 🎉 **节假日检测** - 识别法定节假日、调休工作日和周末
- 🌙 **农历转换** - 提供天干地支、生肖、农历月日信息
- 🌸 **节气计算** - 计算二十四节气信息
- 🤖 **智能注入** - 自动在 LLM Prompt 中注入日期信息
- 🔧 **工具接口** - 提供 Tool 供 LLM 主动查询日期
- 💬 **命令查询** - 支持 `/date` 命令手动查询日期
- 🔄 **优雅降级** - 依赖库缺失时自动降级，确保核心功能可用
- 🚀 **开箱即用** - 安装即可使用，无需复杂配置

## 📖 简介

quick-date-perception 是一个专为 MaiBot 设计的日期感知插件。插件通过在 LLM 调用前自动注入日期感知信息，让麦麦能够准确理解当前时间环境并做出相应回复。

### 🎯 多数据源降级策略

插件采用多层降级策略确保节假日识别功能的可用性：

```
chinese-calendar 库（优先）
    ↓ 不可用
从 unpkg.com 下载节假日数据
    ↓ 下载失败
使用本地缓存数据
    ↓ 缓存不存在
使用内置固定节日列表
    ↓ 最终降级
仅判断周末
```

## 📦 安装

### 方法 1：直接安装（推荐）

1. 将 `quick-date-perception` 文件夹复制到 `MaiBot/plugins/` 目录
2. 重启 MaiBot
3. 插件会自动生成配置文件 `config.toml`

### 方法 2：Git 克隆

```bash
cd MaiBot/plugins/
git clone https://github.com/yourusername/quick-date-perception.git
```

### 验证安装

启动 MaiBot 后，查看日志中是否有：
```
[DatePerception] 插件初始化完成
[DatePerception] 时区配置: Asia/Shanghai
```

## 🔧 依赖管理

### 必需依赖

- Python 3.10+
- MaiBot 0.7.0+

### 可选依赖

插件的所有外部依赖都是**可选的**，不安装时会自动降级：

```bash
# 节假日判断（推荐安装）
pip install chinese-calendar>=1.8.0

# 农历和节气计算（推荐安装）
pip install lunarcalendar>=0.0.9

# 异步 HTTP 客户端（用于下载节假日数据）
pip install aiohttp>=3.8.0
```

### 依赖库说明

| 依赖库 | 用途 | 不安装时的降级行为 |
|--------|------|-------------------|
| `chinese-calendar` | 节假日判断 | 尝试从网络下载节假日数据，失败则使用内置固定节日 |
| `lunarcalendar` | 农历和节气计算 | 跳过农历和节气功能 |
| `aiohttp` | 下载节假日数据 | 仅使用 chinese-calendar 或内置固定节日 |

### 推荐安装方式

```bash
# 完整功能（推荐）
pip install chinese-calendar lunarcalendar aiohttp

# 最小安装（仅基础功能）
# 无需安装任何依赖，插件会自动降级
```

## 🚀 快速开始

### 默认行为

插件安装后即可使用，默认配置：
- ✅ 自动注入日期信息到 LLM Prompt
- ✅ 提供 `/date` 命令查询日期
- ✅ 提供 `get_date_info` 工具供 LLM 调用
- ✅ 启用节假日、农历、节气感知

### 工作原理

```
用户消息
    ↓
EventHandler 拦截
    ↓
生成日期信息
    ↓
注入到 LLM Prompt
    ↓
LLM 处理（带日期上下文）
    ↓
生成回复
```

## 📚 使用说明

### 1. 自动注入模式（推荐）

启用 `enable_event_handler = true` 后，插件会在每次 LLM 调用前自动注入日期信息：

**用户**：今天天气怎么样？

**麦麦**（收到的 Prompt 包含）：
```
【日期】
昨天 | 1月1日 星期一【元旦】
今天 | 1月2日 星期二
明天 | 1月3日 星期三

提示：以上是当前日期信息，可以根据需要融入回复中。

用户消息：今天天气怎么样？
```

**麦麦**：今天是1月2日星期二，天气...

### 2. Tool 工具模式

启用 `enable_tool = true` 后，LLM 可以主动调用 `get_date_info` 工具查询日期：

**用户**：明天是什么日子？

**LLM 决策**：需要查询日期信息 → 调用 `get_date_info` 工具

**工具返回**：
```json
{
  "content": "昨天 | 1月1日 星期一【元旦】\n今天 | 1月2日 星期二\n明天 | 1月3日 星期三",
  "description": "日期信息已获取"
}
```

**麦麦**：明天是1月3日星期三。

### 3. Command 命令模式

启用 `enable_command = true` 后，用户可以使用 `/date` 命令手动查询：

**用户**：`/date`

**麦麦**：
```
昨天 | 1月1日 星期一【元旦】
今天 | 1月2日 星期二
明天 | 1月3日 星期三
```

如果启用了 `enable_llm_expand = true`，输出会更自然：

**麦麦**：
```
昨天是1月1日星期一，元旦假期。
今天是1月2日星期二，正常工作日。
明天是1月3日星期三，也是工作日。
```

## ⚙️ 配置详解

配置文件位置：`MaiBot/plugins/quick-date-perception/config.toml`

### 完整配置示例

```toml
[plugin]
enabled = true              # 是否启用插件
config_version = "1.0.0"    # 配置版本（自动管理）

[perception]
# 时区设置（默认：Asia/Shanghai）
timezone = "Asia/Shanghai"

# 功能开关
enable_holiday = true        # 启用节假日感知
enable_lunar = true          # 启用农历感知
enable_solar_term = true     # 启用节气感知

[components]
# 组件开关
enable_event_handler = true  # 启用自动注入（推荐）
enable_tool = true           # 启用 Tool 工具
enable_command = true        # 启用 /date 命令

[llm]
# LLM 扩展（可选）
enable_llm_expand = false    # 是否使用 LLM 将日期信息转换为自然语言
llm_model = "replyer"        # LLM 模型名称
```

### 配置项说明

#### [plugin] 插件基本信息

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | bool | `true` | 是否启用插件 |
| `config_version` | str | `"1.0.0"` | 配置版本（自动管理） |

#### [perception] 感知功能配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `timezone` | str | `"Asia/Shanghai"` | 时区设置，支持所有 IANA 时区 |
| `enable_holiday` | bool | `true` | 是否启用节假日感知 |
| `enable_lunar` | bool | `true` | 是否启用农历感知（需要 lunarcalendar） |
| `enable_solar_term` | bool | `true` | 是否启用节气感知（需要 lunarcalendar） |

**时区示例**：
- `Asia/Shanghai` - 中国标准时间（UTC+8）
- `Asia/Tokyo` - 日本标准时间（UTC+9）
- `America/New_York` - 美国东部时间（UTC-5/-4）
- `Europe/London` - 英国时间（UTC+0/+1）

完整时区列表：https://en.wikipedia.org/wiki/List_of_tz_database_time_zones

#### [components] 组件开关

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_event_handler` | bool | `true` | 启用自动注入（推荐开启） |
| `enable_tool` | bool | `true` | 启用 Tool 工具接口 |
| `enable_command` | bool | `true` | 启用 `/date` 命令 |

**推荐配置**：
- 日常使用：全部启用
- 仅自动注入：只启用 `enable_event_handler`
- 仅手动查询：只启用 `enable_command`

#### [llm] LLM 扩展配置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enable_llm_expand` | bool | `false` | 是否使用 LLM 转换日期信息为自然语言 |
| `llm_model` | str | `"replyer"` | 使用的 LLM 模型名称 |

**注意**：启用 LLM 扩展会增加响应时间和 API 调用次数，建议仅在需要更自然的输出时启用。

### 常见配置组合

#### 配置 1：完整功能（推荐）

```toml
[perception]
enable_holiday = true
enable_lunar = true
enable_solar_term = true

[components]
enable_event_handler = true
enable_tool = true
enable_command = true

[llm]
enable_llm_expand = false
```

#### 配置 2：仅基础功能

```toml
[perception]
enable_holiday = true
enable_lunar = false
enable_solar_term = false

[components]
enable_event_handler = true
enable_tool = false
enable_command = true
```

#### 配置 3：自然语言输出

```toml
[llm]
enable_llm_expand = true
llm_model = "replyer"
```

#### 配置 4：禁用插件

```toml
[plugin]
enabled = false
```

## 🔍 功能示例

### 节假日识别

```
今天 | 10月1日 星期二【国庆节】
今天 | 2月4日 星期日【春节（调休）】
今天 | 1月20日 星期六【周末】
今天 | 1月15日 星期一【工作日】
```

### 农历信息

```
农历甲辰年(龙年)正月初一
农历乙巳年(蛇年)腊月三十
农历丙午年(马年)闰六月初十
```

### 节气信息

```
今日立春
临近春分（还有2天）
清明已过（2天前）
当前节气: 夏至
```

### 时间段识别

```
上午 (5:00-12:00)
中午 (12:00-14:00)
下午 (14:00-18:00)
晚上 (18:00-22:00)
深夜 (22:00-5:00)
```

## 🛠️ 降级策略详解

### 节假日识别降级

1. **chinese-calendar 可用**（最佳）
   - 使用库的完整节假日数据
   - 支持法定节假日、调休工作日识别
   - 数据最准确、最及时

2. **下载节假日数据**（备用）
   - 从 `unpkg.com` 下载 `holiday-calendar` 数据
   - 缓存到 `data/holidays/{year}.json`
   - 支持法定节假日和调休识别

3. **使用本地缓存**（离线）
   - 读取之前下载的缓存数据
   - 无需网络连接
   - 数据可能不是最新

4. **内置固定节日**（最小）
   - 使用插件内置的固定节日列表
   - 仅包含元旦、劳动节、国庆节等固定日期节日
   - 不支持春节等农历节日和调休识别

5. **仅判断周末**（最终降级）
   - 仅根据星期几判断是否为周末
   - 不识别任何节假日

### 农历和节气降级

- **lunarcalendar 可用**：提供完整的农历和节气信息
- **lunarcalendar 不可用**：跳过农历和节气功能，其他功能正常

### LLM 扩展降级

- **LLM 可用**：将日期信息转换为自然语言
- **LLM 不可用或调用失败**：返回原始格式化信息

## 📝 日志说明

插件使用统一的日志前缀 `[DatePerception]`：

```
[DatePerception] 插件初始化完成
[DatePerception] 时区配置: Asia/Shanghai
[DatePerception] 依赖库状态: chinese-calendar=可用, lunarcalendar=可用
[DatePerception] 注入日期信息: 今天 | 1月2日 星期二
[DatePerception] 警告: chinese-calendar 库未安装，将使用备用方案
[DatePerception] 错误: 时区配置无效: Invalid/Timezone，使用默认时区
```

## 🔧 故障排除

### 问题 1：插件加载失败

**症状：** 启动时没有看到 `[DatePerception]` 日志

**排查步骤：**

1. **检查插件是否启用**
   ```toml
   [plugin]
   enabled = true  # 确保为 true
   ```

2. **检查 MaiBot 版本**
   
   确保 MaiBot 版本 >= 0.7.0

3. **检查文件结构**
   
   确保以下文件存在：
   ```
   MaiBot/plugins/quick-date-perception/
   ├── plugin.py
   ├── _manifest.json
   └── config.toml
   ```

4. **查看完整日志**
   
   查找是否有错误信息

### 问题 2：节假日识别不准确

**症状：** 节假日显示不正确或缺失

**解决方案：**

1. **安装 chinese-calendar 库**（推荐）
   ```bash
   pip install chinese-calendar
   ```

2. **删除缓存重新下载**
   ```bash
   # 删除缓存文件
   rm -rf MaiBot/plugins/quick-date-perception/data/holidays/
   # 重启 MaiBot
   ```

3. **检查网络连接**
   
   确保能访问 `unpkg.com`

4. **检查时区配置**
   ```toml
   [perception]
   timezone = "Asia/Shanghai"  # 确保时区正确
   ```

### 问题 3：农历和节气不显示

**症状：** 没有农历和节气信息

**解决方案：**

1. **安装 lunarcalendar 库**
   ```bash
   pip install lunarcalendar
   ```

2. **检查配置开关**
   ```toml
   [perception]
   enable_lunar = true        # 确保启用
   enable_solar_term = true   # 确保启用
   ```

3. **重启 MaiBot**

### 问题 4：自动注入不生效

**症状：** LLM 回复中没有使用日期信息

**说明：** 这是正常现象。自动注入只是将日期信息添加到 Prompt 中，LLM 是否使用取决于其自身判断。

**如果想强制使用日期信息：**

1. 调整 LLM 的 system prompt
2. 使用 `/date` 命令手动查询
3. 启用 `enable_llm_expand` 获得更自然的输出

### 问题 5：LLM 扩展不生效

**症状：** 启用 `enable_llm_expand` 后输出仍是原始格式

**排查步骤：**

1. **检查配置**
   ```toml
   [llm]
   enable_llm_expand = true
   llm_model = "replyer"  # 确保模型名称正确
   ```

2. **检查 LLM 是否可用**
   
   查看日志中是否有 LLM 调用失败的错误

3. **检查 LLM 配置**
   
   确保 `model_config.toml` 中配置了对应的模型

### 问题 6：时区设置无效

**症状：** 时间显示不正确

**解决方案：**

1. **检查时区格式**
   ```toml
   [perception]
   timezone = "Asia/Shanghai"  # 使用 IANA 时区标识符
   ```

2. **常见时区列表**
   - 中国：`Asia/Shanghai`
   - 日本：`Asia/Tokyo`
   - 美国东部：`America/New_York`
   - 英国：`Europe/London`

3. **查看日志**
   
   日志会显示当前使用的时区

### 调试技巧

**启用详细日志：**

查看日志中的 `[DatePerception]` 标签，了解插件运行状态：

```
[DatePerception] 插件初始化完成
[DatePerception] 时区配置: Asia/Shanghai
[DatePerception] 依赖库状态: chinese-calendar=可用, lunarcalendar=可用
[DatePerception] 注入日期信息: 今天 | 1月2日 星期二
```

**常见日志消息：**

| 日志消息 | 说明 |
|---------|------|
| `插件初始化完成` | 插件加载成功 |
| `时区配置: xxx` | 当前使用的时区 |
| `依赖库状态: xxx` | 依赖库安装情况 |
| `注入日期信息: xxx` | 成功注入日期信息 |
| `警告: xxx` | 非致命错误，插件会降级处理 |
| `错误: xxx` | 严重错误，可能影响功能 |

## � 贡献

欢迎贡献代码、报告问题或提出建议！

### 报告问题

在 [GitHub Issues](https://github.com/sansenjian/quick-date-perception/issues) 提交问题时，请包含：

1. MaiBot 版本
2. 插件版本
3. Python 版本
4. 依赖库安装情况
5. 配置文件内容
6. 相关日志
7. 问题描述和复现步骤

### 提交代码

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feat/amazing-feature`)
3. 提交更改 (`git commit -m '添加某个功能'`)
4. 推送到分支 (`git push origin feat/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源协议。

## 🙏 致谢

- [chinese-calendar](https://github.com/LKI/chinese-calendar) - 提供节假日数据
- [lunarcalendar](https://github.com/wolfhong/LunarCalendar) - 提供农历和节气计算
- [holiday-calendar](https://github.com/NateScarlet/holiday-cn) - 提供节假日数据源

## 📞 联系方式

- GitHub: [@sansenjian](https://github.com/sansenjian)
- Issues: [提交问题](https://github.com/sansenjian/quick-date-perception/issues)

---

<div align="center">

**版本：** 1.0.0  
**兼容性：** MaiBot ≥ 0.7.0 | Python ≥ 3.10  
**更新日期：** 2025-01-19

Made with ❤️ by sansenjian

</div>

## 📝 更新日志

### v1.0.0 (2025-01-19)

**首次发布：**
- 🎉 初始版本发布
- 🕐 时区感知功能
- 📅 日期识别功能
- 🎉 节假日检测功能
- 🌙 农历转换功能
- 🌸 节气计算功能
- 🤖 自动注入功能
- 🔧 Tool 工具接口
- 💬 Command 命令支持
- 🔄 优雅降级机制
- 🧪 完整测试套件

**技术特性：**
- 多数据源降级策略
- 可选依赖管理
- 灵活的配置系统
- 完善的日志记录
- 异步处理支持

---

**注意**：本插件目前处于稳定版本，欢迎反馈问题和建议！
