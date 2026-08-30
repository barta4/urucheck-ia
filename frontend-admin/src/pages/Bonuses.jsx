import { useState } from 'react'
import { Award, Download, FileText, Calendar, CheckCircle2, XCircle, Users, Sparkles, Loader2 } from 'lucide-react'
import api from '../api'
import { useToast } from '../context/ToastContext'

export default function Bonuses() {
  const { success, error: showError, info } = useToast()
  const [month, setMonth] = useState(new Date().toISOString().slice(0, 7))
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [downloadingPdf, setDownloadingPdf] = useState(false)

  const fetchReport = async () => {
    setLoading(true)
    try {
      const res = await api.get('/dashboard/bonus-report', { params: { month } })
      setReport(res.data)
      success(`Reporte del período ${month} generado`)
    } catch (e) {
      showError('Error al generar el reporte de bonos')
    } finally {
      setLoading(false)
    }
  }

  const exportCSV = () => {
    window.open(`/api/dashboard/bonus-report/export?month=${month}`, '_blank')
    info('Descargando archivo CSV...')
  }

  const exportPDF = async () => {
    setDownloadingPdf(true)
    try {
      const response = await api.get('/dashboard/bonus-report/pdf', {
        params: { month },
        responseType: 'blob'
      })
      const blob = new Blob([response.data], { type: 'application/pdf' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `reporte_oficial_bonos_${month}.pdf`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      success('Reporte PDF oficial descargado exitosamente')
    } catch (e) {
      showError('Error al generar el documento PDF')
    } finally {
      setDownloadingPdf(false)
    }
  }

  const reportList = Array.isArray(report?.report) ? report.report : []
  const totalEvaluated = reportList.length
  const totalEarned = reportList.filter(r => r.bonus_earned).length
  const totalNotEarned = totalEvaluated - totalEarned

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 tracking-tight flex items-center gap-2">
            <Award className="w-7 h-7 text-amber-500" />
            Reporte Mensual de Puntualidad & Bonos
          </h2>
          <p className="text-sm text-gray-500 mt-1">
            Calcula automáticamente el cumplimiento de metas de presentismo y exporta planillas oficiales.
          </p>
        </div>

        {report && (
          <div className="flex items-center gap-2.5 flex-wrap">
            <button
              onClick={exportCSV}
              className="px-3.5 py-2 bg-white border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 shadow-sm flex items-center gap-2 transition"
            >
              <Download className="w-4 h-4 text-gray-500" />
              Exportar CSV
            </button>
            <button
              onClick={exportPDF}
              disabled={downloadingPdf}
              className="px-4 py-2 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 shadow-sm flex items-center gap-2 transition disabled:opacity-50"
            >
              {downloadingPdf ? <Loader2 className="w-4 h-4 animate-spin" /> : <FileText className="w-4 h-4" />}
              {downloadingPdf ? 'Generando PDF...' : 'Descargar PDF Oficial (con QR)'}
            </button>
          </div>
        )}
      </div>

      {/* Filter Selector */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 flex flex-wrap gap-4 items-end">
        <div className="w-64">
          <label className="block text-xs font-semibold uppercase text-gray-600 mb-1.5 flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5 text-blue-600" />
            Mes a Evaluar
          </label>
          <input
            type="month"
            value={month}
            onChange={e => setMonth(e.target.value)}
            className="w-full border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500"
          />
        </div>
        <button
          onClick={fetchReport}
          disabled={loading}
          className="px-5 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-semibold hover:bg-blue-700 shadow-sm transition disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          {loading ? 'Calculando...' : 'Generar Reporte'}
        </button>
      </div>

      {/* KPI Cards */}
      {report && !loading && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                <Users className="w-6 h-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{totalEvaluated}</p>
                <p className="text-xs font-medium text-gray-500 mt-0.5">Empleados Evaluados</p>
              </div>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 flex items-center justify-center text-emerald-600 shrink-0">
                <CheckCircle2 className="w-6 h-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-emerald-600">{totalEarned}</p>
                <p className="text-xs font-medium text-gray-500 mt-0.5">Bono Ganado (100% Puntual)</p>
              </div>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex items-center gap-4">
              <div className="w-12 h-12 rounded-xl bg-amber-50 flex items-center justify-center text-amber-600 shrink-0">
                <XCircle className="w-6 h-6" />
              </div>
              <div>
                <p className="text-2xl font-bold text-amber-600">{totalNotEarned}</p>
                <p className="text-xs font-medium text-gray-500 mt-0.5">Sin Bono (Días insuficientes)</p>
              </div>
            </div>
          </div>

          {/* Table Card */}
          <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50/80 text-gray-600 text-xs uppercase tracking-wider font-semibold border-b border-gray-100">
                  <tr>
                    <th className="px-6 py-4">Empleado</th>
                    <th className="px-6 py-4">Email</th>
                    <th className="px-6 py-4 text-center">Días Puntual</th>
                    <th className="px-6 py-4 text-center">Meta Requerida</th>
                    <th className="px-6 py-4 text-center">Resultado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {report.report.map(row => (
                    <tr key={row.employee_id} className="hover:bg-gray-50/70 transition-colors">
                      <td className="px-6 py-4 font-semibold text-gray-900">{row.employee_name}</td>
                      <td className="px-6 py-4 text-gray-500">{row.email}</td>
                      <td className="px-6 py-4 text-center">
                        <span className="font-bold text-gray-900 font-mono text-sm bg-gray-100 px-2.5 py-1 rounded-lg">
                          {row.on_time_days}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center text-gray-500 font-mono text-xs">
                        {row.required_days} días
                      </td>
                      <td className="px-6 py-4 text-center">
                        {row.bonus_earned ? (
                          <span className="inline-flex items-center gap-1.5 bg-emerald-50 text-emerald-700 border border-emerald-200 px-3 py-1 rounded-full text-xs font-bold">
                            <Award className="w-3.5 h-3.5 text-emerald-600" />
                            Asegurado
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 bg-gray-100 text-gray-500 px-3 py-1 rounded-full text-xs font-medium">
                            No alcanzado
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
