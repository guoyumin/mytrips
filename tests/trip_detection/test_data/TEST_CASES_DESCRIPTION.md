# Trip Detection Test Cases Description

## Level 1: Single Booking (已实现)
- **single_flight_booking.json**: 基础往返航班测试
  - 验证单一预订的行程边界识别
  - 验证基本字段映射

## Level 2: Multi-Booking Combinations
### 2.1 multi_booking_flight_hotel.json
- **场景**: 连接航班(ZRH→CDG→BCN) + 酒店 + 返程航班
- **验证点**:
  - 多个邮件正确组合为一个行程
  - 航班段按时间顺序排列
  - 酒店与行程日期匹配
  - 总费用 = 450(去程) + 360(酒店) + 180(返程) = 990 EUR

### 2.2 flight_with_activities.json
- **场景**: 罗马往返航班 + 多个旅游活动
- **验证点**:
  - 活动正确关联到行程
  - 活动按日期排序
  - 不同类型活动的正确分类

## Level 3: Existing Trip Merging
### 3.1 existing_paris_trip.json + new_louvre_booking.json
- **场景**: 向已有巴黎行程添加卢浮宫门票
- **验证点**:
  - 识别新活动属于现有行程(日期匹配)
  - 正确更新活动列表
  - 保留原有预订信息
  - 更新总费用: 850 + 17 = 867 EUR

### 3.2 extend_london_to_edinburgh.json
- **场景**: 伦敦3天行程延伸到爱丁堡2天
- **验证点**:
  - 识别为同一行程的延伸(连续日期)
  - 更新结束日期: 3/18 → 3/20
  - 添加新城市: [Zurich, London, Edinburgh, Zurich]
  - 处理多种交通方式(飞机+火车)
  - 原返程航班应被替换

## Level 4: Booking Modifications
### 4.1 flight_modification.json
- **场景**: 航班时间变更(同确认号)
- **验证点**:
  - 识别为同一预订的更新
  - 只保留最新版本active
  - 原始航班标记为modified
  - 确认号保持不变: LH2025ABC

### 4.2 cancel_and_rebook.json
- **场景**: 取消原酒店，预订新酒店
- **验证点**:
  - 原预订标记为cancelled
  - 新预订为active
  - 费用只计算新酒店: 890 EUR
  - 两个预订都保留在系统中

## Level 5: Edge Cases
### 5.1 cross_year_trip.json
- **场景**: 12/28/2024 - 01/03/2025 跨年旅行
- **验证点**:
  - 正确处理跨年日期
  - 行程持续时间: 7天
  - 年份变化不影响行程完整性

### 5.2 same_day_trips.json
- **场景**: 同一天出发的两个行程
- **验证点**:
  - 识别为两个独立行程:
    - 行程1: 慕尼黑商务(当天往返)
    - 行程2: 米兰周末(6/15晚-6/17)
  - 基于时间和目的地区分
  - 商务行程特征: 同日往返
  - 休闲行程特征: 跨夜住宿

## 测试执行注意事项

1. **AI响应变异性**: AI可能对行程名称、描述有不同理解，验证应聚焦于核心数据
2. **费用容差**: 允许小幅费用计算差异(如汇率转换)
3. **时区处理**: 确保跨时区航班的时间正确
4. **确认号追踪**: 验证修改/取消场景下的确认号关联

## 扩展测试想法

- 多目的地环游(5+城市)
- 邮轮行程处理
- 部分取消(如取消多段行程中的一段)
- 数据不完整场景(缺少关键信息)
- 极端案例(超长行程、大量预订等)