import { useState, useRef, useEffect } from 'react'
import api from '../api'

export default function AiChat() {
    const [messages, setMessages] = useState([
        { role: 'ai', text: '¡Hola! Soy tu asistente de asistencia. ¿Qué te gustaría saber sobre el presentismo de hoy?' }
    ])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const bottomRef = useRef(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    const handleSubmit = async (e) => {
        e.preventDefault()
        if (!input.trim() || loading) return

        const userText = input.trim()
        setInput('')
        setMessages(prev => [...prev, { role: 'user', text: userText }])
        setLoading(true)

        try {
            const res = await api.post('/chat/', { message: userText })
            setMessages(prev => [...prev, { role: 'ai', text: res.data.reply }])
        } catch (err) {
            setMessages(prev => [...prev, { role: 'ai', text: 'Oops. Ocurrió un error conectando con el servidor de IA.' }])
        } finally {
            setLoading(false)
        }
    }

    const [isOpen, setIsOpen] = useState(false)

    if (!isOpen) {
        return (
            <button
                onClick={() => setIsOpen(true)}
                className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 rounded-full shadow-xl flex items-center justify-center text-white text-2xl hover:bg-blue-700 hover:scale-105 transition-all z-[9999]"
            >
                <svg className="w-7 h-7" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
            </button>
        )
    }

    return (
        <div className="fixed bottom-6 right-6 w-80 md:w-96 shadow-2xl rounded-2xl flex flex-col bg-white overflow-hidden z-[9999] border border-gray-200" style={{ height: '500px', maxHeight: '80vh' }}>
            <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 text-lg">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"></path></svg>
                    </div>
                    <div>
                        <h2 className="font-bold text-gray-900 leading-tight text-sm">Agente IA</h2>
                        <p className="text-[10px] text-gray-500">Conectado en tiempo real</p>
                    </div>
                </div>
                <button
                    onClick={() => setIsOpen(false)}
                    className="text-gray-400 hover:text-gray-600 w-8 h-8 rounded-full hover:bg-gray-200 flex items-center justify-center transition"
                >
                    ✕
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-4">
                {messages.map((m, i) => (
                    <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                        <div
                            className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm shadow-sm
                ${m.role === 'user'
                                    ? 'bg-blue-600 text-white rounded-tr-none'
                                    : 'bg-gray-100 text-gray-800 rounded-tl-none whitespace-pre-wrap'
                                }`}
                        >
                            {m.text}
                        </div>
                    </div>
                ))}
                {loading && (
                    <div className="flex justify-start">
                        <div className="bg-gray-100 rounded-2xl rounded-tl-none px-4 py-3 shadow-sm flex gap-1">
                            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce"></span>
                            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '150ms' }}></span>
                            <span className="w-2 h-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: '300ms' }}></span>
                        </div>
                    </div>
                )}
                <div ref={bottomRef} />
            </div>

            <div className="p-3 border-t bg-gray-50">
                <form onSubmit={handleSubmit} className="flex gap-2">
                    <input
                        type="text"
                        value={input}
                        onChange={(e) => setInput(e.target.value)}
                        placeholder="Pregunta algo..."
                        className="flex-1 border border-gray-300 rounded-full px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                        disabled={loading}
                    />
                    <button
                        type="submit"
                        disabled={loading || !input.trim()}
                        className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center hover:bg-blue-700 disabled:opacity-50 transition flex-shrink-0"
                    >
                        ➤
                    </button>
                </form>
            </div>
        </div>
    )
}
