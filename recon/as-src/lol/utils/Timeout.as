class lol.utils.Timeout
{
   var id;
   static var _intervals = new Array();
   function Timeout()
   {
      this.id = lol.utils.Timeout._intervals.length;
      lol.utils.Timeout._intervals[this.id] = setInterval(function(i, a)
      {
         a[1].apply(a[0],a.splice(3,a.length));
         clearInterval(lol.utils.Timeout._intervals[i]);
      }
      ,arguments[2],this.id,arguments);
   }
   function Clear()
   {
      clearInterval(lol.utils.Timeout._intervals[this.id]);
   }
}
