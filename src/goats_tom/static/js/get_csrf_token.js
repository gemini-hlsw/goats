/**
* Retrieves the CSRF token from the cookies.
*
* Django sets a CSRF token in the cookies for the protection against CSRF
* attacks. This function reads the CSRF token from the cookies and returns it.
*
* @return {string} The CSRF token.
*/
const getCsrfToken = () => {
  const csrfToken = document.cookie.split('; ').find(row => row.startsWith('csrftoken='));
  return csrfToken ? csrfToken.split('=')[1] : '';
};