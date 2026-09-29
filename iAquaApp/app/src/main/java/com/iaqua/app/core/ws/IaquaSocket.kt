package com.iaqua.app.core.ws

import com.iaqua.app.core.protocol.HistResponse
import com.iaqua.app.core.protocol.IaquaProtocol
import com.iaqua.app.core.protocol.WsFrame
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import javax.inject.Inject
import javax.inject.Singleton

/** 连接状态 */
sealed interface ConnState {
    data object Disconnected : ConnState
    data object Connecting : ConnState
    data class Connected(val url: String) : ConnState
    data class Failed(val reason: String) : ConnState
}

/** WS 事件流：状态变化或协议帧 */
sealed interface SocketEvent {
    data class State(val state: ConnState) : SocketEvent
    data class Frame(val frame: WsFrame) : SocketEvent
    data class Hist(val data: HistResponse) : SocketEvent
}

/**
 * 单缸 WS 连接（协议与 Web 仪表盘一致）。
 * M1 局域网直连 ws://<ip>/ws；Windows 主机环境请直接使用设备 IP（不支持 .local mDNS 解析）。
 */
@Singleton
class IaquaSocket @Inject constructor(
    private val client: OkHttpClient,
) {
    private var ws: WebSocket? = null

    /** 建立连接并持续接收帧；重复调用会先断开旧连接 */
    fun connect(url: String): Flow<SocketEvent> = callbackFlow {
        trySend(SocketEvent.State(ConnState.Connecting))
        val request = Request.Builder().url(url).build()
        val socket = client.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                trySend(SocketEvent.State(ConnState.Connected(url)))
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { IaquaProtocol.json.decodeFromString(WsFrame.serializer(), text) }
                    .onSuccess { trySend(SocketEvent.Frame(it)) }
                if (text.contains("\"hist\"")) {
                    runCatching { IaquaProtocol.json.decodeFromString(HistResponse.serializer(), text) }
                        .onSuccess { trySend(SocketEvent.Hist(it)) }
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                trySend(SocketEvent.State(ConnState.Failed(t.message ?: "连接失败")))
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                trySend(SocketEvent.State(ConnState.Disconnected))
            }
        })
        ws = socket
        awaitClose { socket.close(1000, "client closed") }
    }

    fun send(text: String): Boolean = ws?.send(text) ?: false

    fun disconnect() {
        ws?.close(1000, "bye")
        ws = null
    }

    /** 连通性测试（添加缸时使用）：建立连接拿到结果后立即断开 */
    suspend fun probe(url: String, timeoutMs: Long = 3_000): Boolean {
        val ev = withTimeoutOrNull(timeoutMs) {
            connect(url).first { it is SocketEvent.State && it.state !is ConnState.Connecting }
        }
        disconnect()
        return ev is SocketEvent.State && ev.state is ConnState.Connected
    }
}
