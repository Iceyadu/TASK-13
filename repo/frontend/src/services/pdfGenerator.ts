import { jsPDF } from 'jspdf'

export function generateReceiptPdf(data: {
  receiptNumber: string
  residentName: string
  propertyName: string
  paymentDate: string
  paymentMethod: string
  amount: string
  billReference: string
}): Blob {
  const doc = new jsPDF()
  doc.setFontSize(20)
  doc.setTextColor(26, 60, 94)
  doc.text('Payment Receipt', 20, 25)

  doc.setFontSize(11)
  doc.setTextColor(0)
  let y = 40
  const entries = [
    ['Receipt #', data.receiptNumber],
    ['Date', data.paymentDate],
    ['Property', data.propertyName],
    ['Resident', data.residentName],
    ['Bill Reference', data.billReference],
    ['Payment Method', data.paymentMethod],
    ['Amount Paid', `$${data.amount}`],
  ]
  for (const [label, value] of entries) {
    doc.setFont('helvetica', 'bold')
    doc.text(`${label}:`, 20, y)
    doc.setFont('helvetica', 'normal')
    doc.text(value, 70, y)
    y += 8
  }

  y += 10
  doc.setFontSize(8)
  doc.setTextColor(128)
  doc.text(`HarborView Property Operations Portal — Generated ${new Date().toISOString().slice(0, 16)} UTC`, 20, y)

  return doc.output('blob')
}

export function generateStatementPdf(data: {
  propertyName: string
  residentName: string
  unitNumber: string
  billingPeriod: string
  dueDate: string
  lineItems: Array<{ description: string; amount: string; tax: string; total: string }>
  total: string
}): Blob {
  const doc = new jsPDF()
  doc.setFontSize(20)
  doc.setTextColor(26, 60, 94)
  doc.text('Billing Statement', 20, 25)

  doc.setFontSize(11)
  doc.setTextColor(0)
  let y = 40
  doc.text(`Property: ${data.propertyName}  |  Resident: ${data.residentName}  |  Unit: ${data.unitNumber}`, 20, y)
  y += 8
  doc.text(`Period: ${data.billingPeriod}  |  Due Date: ${data.dueDate}`, 20, y)
  y += 12

  // Table header
  doc.setFont('helvetica', 'bold')
  doc.text('Description', 20, y)
  doc.text('Amount', 100, y)
  doc.text('Tax', 130, y)
  doc.text('Total', 160, y)
  y += 2
  doc.line(20, y, 190, y)
  y += 6

  doc.setFont('helvetica', 'normal')
  for (const item of data.lineItems) {
    doc.text(item.description, 20, y)
    doc.text(`$${item.amount}`, 100, y)
    doc.text(`$${item.tax}`, 130, y)
    doc.text(`$${item.total}`, 160, y)
    y += 7
  }

  y += 4
  doc.setFont('helvetica', 'bold')
  doc.text('Total Due', 20, y)
  doc.text(`$${data.total}`, 160, y)

  return doc.output('blob')
}
