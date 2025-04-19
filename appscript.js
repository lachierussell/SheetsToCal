/**
This needs to be added to google sheets 'Extensions->Appscript'
 */

const API_BASE_URL = ""
const API_KEY = ""


function sendSheetAsCSV() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  const data = sheet.getDataRange().getValues();
  
  // Convert 2D array to CSV string
  const csv = data.map(row => 
	row.map(value => `"${String(value).replace(/"/g, '""')}"`).join(',')
  ).join('\n');

  const payload = {
	method: 'post',
	contentType: 'application/json',
	payload: JSON.stringify({ calendar: csv }),
	headers: {
	  'x-api-key': `${API_KEY}`
	},
	muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(`${API_BASE_URL}/update`, payload);
  Logger.log(response.getContentText());
}