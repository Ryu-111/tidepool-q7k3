// Shared checker for the synthetic pattern pages. Each page sets window.EXPECTED (name -> value);
// for <select> the value is the selected option's text. Nothing is submitted anywhere.
(() => {
  const form = () => document.querySelector('#fixture');
  const current = el => el.tagName === 'SELECT' ? el.selectedOptions[0]?.text ?? '' : el.value;
  window.probeReady = () => Object.keys(window.EXPECTED).every(name => {
    const el = form().elements[name];
    return el && (el.tagName === 'SELECT' ? el.selectedIndex === 0 : el.value === '');
  });
  document.querySelector('#verify').onclick = () => {
    const wrong = Object.entries(window.EXPECTED)
      // An array lists every acceptable outcome, e.g. ['検証町1-2-3', ''] = right kind or left empty.
      .filter(([name, value]) => ![].concat(value).includes(current(form().elements[name])))
      .map(([name]) => name);
    document.querySelector('#result').textContent = wrong.length === 0
      ? 'PASS: ' + Object.keys(window.EXPECTED).length + '項目を期待どおり入力'
      : 'FAIL: ' + wrong.join(', ');
  };
})();
