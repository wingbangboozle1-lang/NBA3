
// client-side table filter and sort - no dependencies, no network calls
(function(){
  var tables=[].slice.call(document.querySelectorAll('table[data-rows]'));
  if(!tables.length)return;
  var box=document.createElement('div');box.className='f';
  box.innerHTML='<label for="q">Filter rows on this page</label><input id="q" type="search" placeholder="team, player, STR-06, flagged…" autocomplete="off">';
  tables[0].parentNode.parentNode.insertBefore(box,tables[0].parentNode);
  box.querySelector('input').addEventListener('input',function(e){
    var v=e.target.value.toLowerCase();
    tables.forEach(function(t){
      [].slice.call(t.querySelectorAll('tbody tr')).forEach(function(tr){
        tr.style.display=!v||tr.textContent.toLowerCase().indexOf(v)>-1?'':'none';
      });
    });
  });
  tables.forEach(function(t){
    [].slice.call(t.querySelectorAll('th')).forEach(function(th,i){
      th.style.cursor='pointer';th.title='sort';
      th.addEventListener('click',function(){
        var tb=t.querySelector('tbody'),rs=[].slice.call(tb.querySelectorAll('tr'));
        var dir=th.dataset.d=th.dataset.d==='a'?'z':'a';
        rs.sort(function(a,b){
          var x=a.children[i]?a.children[i].textContent.trim():'',y=b.children[i]?b.children[i].textContent.trim():'';
          var nx=parseFloat(x.replace(/[^0-9.\-+]/g,'')),ny=parseFloat(y.replace(/[^0-9.\-+]/g,''));
          var c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y));
          return dir==='a'?c:-c;
        });
        rs.forEach(function(r){tb.appendChild(r)});
      });
    });
  });
})();
