/**
 * Utility helpers for browser file downloads (Blobs, CSV, Excel, PDF).
 */

export function downloadBlob(blobData, filename, mimeType = 'application/octet-stream') {
  if (!blobData) return
  const blob = blobData instanceof Blob ? blobData : new Blob([blobData], { type: mimeType })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

export function downloadCsvFromData(filename, headers, rows) {
  if (!rows || rows.length === 0) return
  const formattedRows = rows.map(r =>
    r.map(val => {
      if (val === null || val === undefined) return '""'
      const str = String(val)
      return `"${str.replace(/"/g, '""')}"`
    }).join(',')
  )
  const csvContent = '\uFEFF' + [headers.join(','), ...formattedRows].join('\n')
  downloadBlob(csvContent, filename, 'text/csv;charset=utf-8;')
}
