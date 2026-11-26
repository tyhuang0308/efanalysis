// 網站設定：產生報告書用的Google登入、試算表和範本
// 這些值都不是密碼，放在公開的GitHub上沒有關係；
// 只有試算表和範本有分享給他的人，登入後才讀得到內容
window.EF_CONFIG = {
  // Google Cloud「用戶端」頁面的用戶端ID（結尾是 .apps.googleusercontent.com）
  googleClientId: '',

  // 共享試算表「narrative&EF&ER資料key in」：網址 /d/ 和 /edit 中間那一段
  sheetId: '1y75at9jREamKqjykwqohKsmnqSxB5xkLhu8cCaZ59Lo',
  // 產生報告書用的工作表名稱
  sheetName: 'report',

  // Google Drive上的 report template.docx：網址 /d/ 和 /edit 中間那一段
  templateId: '1aMPTZSZQ9S1b4NjNu65s6GtSdY5AKrGd',
};
