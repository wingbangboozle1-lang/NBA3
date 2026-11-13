document.querySelectorAll('input[data-filter-table]').forEach(function(inp){
  var t=document.getElementById(inp.getAttribute('data-filter-table'));
  if(!t)return;
  inp.addEventListener('input',function(){
    var q=inp.value.toLowerCase();
    t.querySelectorAll('tbody tr').forEach(function(tr){
      tr.style.display = tr.textContent.toLowerCase().indexOf(q)>-1 ? '' : 'none';
    });
  });
});
