package com.iaqua.app.data.repo

import com.iaqua.app.alerts.AlertEngine
import com.iaqua.app.core.protocol.HistResponse
import com.iaqua.app.core.protocol.IaquaProtocol
import com.iaqua.app.core.ws.ConnState
import com.iaqua.app.core.ws.IaquaSocket
import com.iaqua.app.core.ws.SocketEvent
import com.iaqua.app.data.db.AlertDao
import com.iaqua.app.data.db.AlertEventEntity
import com.iaqua.app.data.db.AlertRuleEntity
import com.iaqua.app.data.db.TankEntity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import javax.inject.Inject
import javax.inject.Singleton

/** 当前缸遥测快照（缺测为 null，与 Web 端一致按 null 断线处理） */
data class TelSnapshot(
    val temp: Double? = null,
    val ph: Double? = null,
    val orp: Double? = null,
    val mtemp: Double? = null,
    val tds1: Double? = null,
    val tds2: Double? = null,
    val lux: Double? = null,
    val lvl: Double? = null,
    val ts: Long = 0,
) {
    companion object {
        fun from(f: com.iaqua.app.core.protocol.WsFrame) = TelSnapshot(
            temp = f.temp, ph = f.ph, orp = f.orp, mtemp = f.mtemp,
            tds1 = f.tds1, tds2 = f.tds2, lux = f.lux, lvl = f.lvl,
            ts = System.currentTimeMillis(),
        )
    }
}

/**
 * 设备连接与数据仓库（方案 §6.3）：
 * 缸切换自动断开重连；M1 直连主板 WS，二期升级 MQTT 上云。
 * 同时驱动阈值告警引擎（方案 §5.1）。
 */
@Singleton
class DeviceRepository @Inject constructor(
    private val socket: IaquaSocket,
    private val tankRepo: TankRepository,
    private val alertDao: AlertDao,
    private val alertEngine: AlertEngine,
    private val scope: CoroutineScope,
) {
    private val _telemetry = MutableStateFlow(TelSnapshot())

    /** 当前缸遥测快照 */
    val telemetry: StateFlow<TelSnapshot> = _telemetry.asStateFlow()

    @OptIn(ExperimentalCoroutinesApi::class)
    val connState: StateFlow<ConnState> = tankRepo.activeTank
        .map { it?.deviceWs }
        .distinctUntilChanged()
        .flatMapLatest { url ->
            if (url.isNullOrBlank()) flowOf(SocketEvent.State(ConnState.Disconnected))
            else socket.connect(url)
        }
        .map { ev -> (ev as? SocketEvent.State)?.state ?: ConnState.Disconnected }
        .stateIn(scope, SharingStarted.Eagerly, ConnState.Disconnected)

    /** 当前缸的帧事件流（切缸自动切换收集目标） */
    @OptIn(ExperimentalCoroutinesApi::class)
    private val frames: Flow<Pair<TankEntity, SocketEvent>> = tankRepo.activeTank
        .flatMapLatest { tank ->
            if (tank == null) emptyFlow()
            else socket.events.map { tank to it }
        }

    init {
        // 收包：更新遥测 + 评估阈值规则（免打扰/通知在 Notifier 内做）
        scope.launch {
            frames.collect { (tank, ev) ->
                if (ev is SocketEvent.Frame) {
                    val snap = TelSnapshot.from(ev.frame)
                    _telemetry.value = snap
                    evaluateRules(tank, snap)
                }
            }
        }
    }

    private suspend fun evaluateRules(tank: TankEntity, snap: TelSnapshot) {
        // TODO(M1-优化): 规则缓存，避免每帧查库（当前 1Hz 频率可接受）
        val rules = alertDao.enabledRules(tank.id)
        val now = System.currentTimeMillis()
        for (rule in rules) {
            val value = rule.metricValue(snap) ?: continue
            val event = alertEngine.evaluate(rule, value, now) ?: continue
            alertDao.insertEvent(event.copy(snapshot = value.toString()))
        }
    }

    /** 拉取历史数据（24h/7d/30d/1y），超时或无回包返回 null */
    suspend fun fetchHist(hours: Int): HistResponse? {
        if (!socket.send(IaquaProtocol.histRequest(hours))) return null
        return withTimeoutOrNull(4_000) {
            socket.events.filterIsInstance<SocketEvent.Hist>().first().data
        }
    }

    /** 连通性测试（添加缸） */
    suspend fun probe(url: String): Boolean = socket.probe(url)
}

/** 按指标名取遥测值 */
fun AlertRuleEntity.metricValue(s: TelSnapshot): Double? = when (metric) {
    "temp" -> s.temp
    "ph" -> s.ph
    "orp" -> s.orp
    "mtemp" -> s.mtemp
    "tds1" -> s.tds1
    "tds2" -> s.tds2
    "lux" -> s.lux
    "lvl" -> s.lvl
    else -> null
}
