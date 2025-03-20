function toggleUserInfoForm() {
    const formDiv = document.getElementById('userInfoForm');
    if (formDiv.style.display === 'none' || formDiv.style.display === '') {
        formDiv.style.display = 'block';
    } else {
        formDiv.style.display = 'none';
    }
}


function toggleCreateGroupForm() {
  const form = document.getElementById('createGroupForm');
  if (!form) return;
  form.style.display = (form.style.display === 'none' || form.style.display === '')
                        ? 'block'
                        : 'none';
}
