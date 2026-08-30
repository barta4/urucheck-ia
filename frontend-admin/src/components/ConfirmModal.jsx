import { useEffect } from 'react'
import { AlertTriangle, AlertCircle, Info, Loader2 } from 'lucide-react'

export default function ConfirmModal({
  isOpen,
  title = '¿Estás seguro?',
  message = 'Esta acción no se puede deshacer.',
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  confirmVariant = 'danger', // 'danger' | 'primary' | 'warning'
  onConfirm,
  onCancel,
  loading = false,
}) {
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && isOpen && !loading) {
        onCancel?.()
      }
    }
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'hidden'
    }
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
      document.body.style.overflow = 'unset'
    }
  }, [isOpen, loading, onCancel])

  if (!isOpen) return null

  const getVariantStyles = () => {
    switch (confirmVariant) {
      case 'danger':
        return {
          icon: <AlertCircle className="w-6 h-6 text-red-600" />,
          iconBg: 'bg-red-100',
          buttonBg: 'bg-red-600 hover:bg-red-700 text-white focus:ring-red-500',
        }
      case 'warning':
        return {
          icon: <AlertTriangle className="w-6 h-6 text-amber-600" />,
          iconBg: 'bg-amber-100',
          buttonBg: 'bg-amber-600 hover:bg-amber-700 text-white focus:ring-amber-500',
        }
      default:
        return {
          icon: <Info className="w-6 h-6 text-blue-600" />,
          iconBg: 'bg-blue-100',
          buttonBg: 'bg-blue-600 hover:bg-blue-700 text-white focus:ring-blue-500',
        }
    }
  }

  const styles = getVariantStyles()

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" aria-labelledby="modal-title" role="dialog" aria-modal="true">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-gray-900/50 backdrop-blur-sm transition-opacity"
        onClick={() => !loading && onCancel?.()}
      />

      <div className="flex min-h-full items-center justify-center p-4 text-center sm:p-0">
        <div className="relative transform overflow-hidden rounded-2xl bg-white text-left shadow-2xl transition-all sm:my-8 sm:w-full sm:max-w-lg border border-gray-100">
          <div className="bg-white px-6 pt-6 pb-4 sm:p-6 sm:pb-4">
            <div className="sm:flex sm:items-start gap-4">
              <div className={`mx-auto flex h-12 w-12 shrink-0 items-center justify-center rounded-xl sm:mx-0 ${styles.iconBg}`}>
                {styles.icon}
              </div>
              <div className="mt-3 text-center sm:mt-0 sm:text-left flex-1">
                <h3 className="text-lg font-semibold leading-6 text-gray-900" id="modal-title">
                  {title}
                </h3>
                <div className="mt-2">
                  <p className="text-sm text-gray-600 whitespace-pre-line">
                    {message}
                  </p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 px-6 py-4 sm:flex sm:flex-row-reverse sm:px-6 gap-3">
            <button
              type="button"
              disabled={loading}
              onClick={onConfirm}
              className={`inline-flex w-full justify-center items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 sm:w-auto transition-all disabled:opacity-50 ${styles.buttonBg}`}
            >
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {confirmText}
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={onCancel}
              className="mt-3 inline-flex w-full justify-center rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-gray-700 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto transition-all disabled:opacity-50"
            >
              {cancelText}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
