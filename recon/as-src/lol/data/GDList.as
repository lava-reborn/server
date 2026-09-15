class lol.data.GDList
{
   var list;
   function GDList(arr)
   {
      if(arr)
      {
         this.list = arr;
      }
      else
      {
         this.list = new Array();
      }
   }
   function push(val)
   {
      this.list.push(val);
   }
   function unshift(val)
   {
      this.list.unshift(val);
   }
   function shift()
   {
      return this.list.shift();
   }
   function pop()
   {
      return this.list.pop();
   }
   function splice(i, l, val)
   {
      return this.list.splice(i,l,val);
   }
   function toString()
   {
      return "|" + this.list.join("|") + "|";
   }
}
