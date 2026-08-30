import { createContext, useContext, useState, useCallback } from 'react'
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 9)
    const newToast = { id, message, type }
    setToasts((prev) => [...prev, newToast])

    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }
  }, [removeToast])

  const success = useCallback((msg, duration) => showToast(msg, 'success', duration), [showToast])
  const error = useCallback((msg, duration) => showToast(msg, 'error', duration || 5000), [showToast])
  const info = useCallback((msg, duration) => showToast(msg, 'info', duration), [showToast])
  const warning = useCallback((msg, duration) => showToast(msg, 'warning', duration), [showToast])

  return (
    <ToastContext.Provider value={{ showToast, success, error, info, warning }}>
      {children}
      {/* Toast Render Container */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 max-w-sm w-full pointer-events-none px-4 sm:px-0">
        {toasts.map((toast) => {
          const isSuccess = toast.type === 'success'
          const isError = toast.type === 'error'
          const isWarning = toast.type === 'warning'
          
          let bgClasses = 'bg-white border-blue-200 text-gray-800'
          let icon = <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />

          if (isSuccess) {
            bgClasses = 'bg-white border-emerald-200 text-gray-800'
            icon = <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0 mt-0.5" />
          } else if (isError) {
            bgClasses = 'bg-white border-red-200 text-gray-800'
            icon = <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
          } else if (isWarning) {
            bgClasses = 'bg-white border-amber-200 text-gray-800'
            icon = <AlertTriangle className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
          }

          return (
            <div
              key={toast.id}
              role="alert"
              className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl border shadow-lg transition-all duration-300 transform translate-y-0 opacity-100 ${bgClasses}`}
            >
              {icon}
              <div className="flex-1 text-sm font-medium leading-5">
                {toast.message}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="text-gray-400 hover:text-gray-600 transition-colors p-0.5 -mr-1"
                aria-label="Cerrar notificación"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast debe ser utilizado dentro de un ToastProvider')
  }
  return context
}
