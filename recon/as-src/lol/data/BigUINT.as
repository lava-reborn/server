class lol.data.BigUINT
{
   var clusterList;
   function BigUINT()
   {
      this.clusterList = new Array();
      if(arguments)
      {
         this.init(arguments);
      }
   }
   function init(arr)
   {
      var _loc4_ = arr.length;
      var _loc2_ = 0;
      while(_loc2_ < _loc4_)
      {
         if(arr[_loc2_] instanceof lol.data.BigUINTCluster)
         {
            this.clusterList.push(arr[_loc2_]);
         }
         else
         {
            trace("Error: argument must be BigUINTCluster instance");
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function addCluster()
   {
      if(arguments[0] instanceof lol.data.BigUINTCluster)
      {
         this.clusterList.push(arguments[0]);
      }
      else
      {
         this.clusterList.push(new lol.data.BigUINTCluster(arguments[0],arguments[1]));
      }
   }
   function addClusterAt()
   {
      if(arguments[0] instanceof lol.data.BigUINTCluster)
      {
         this.clusterList.splice(arguments[1],0,arguments[0]);
      }
      else
      {
         this.clusterList.splice(arguments[2],0,new lol.data.BigUINTCluster(arguments[0],arguments[1]));
      }
   }
   function shift()
   {
      return this.clusterList.shift();
   }
   function pop()
   {
      return this.clusterList.pop();
   }
   function toString()
   {
      var _loc3_ = "x";
      var _loc4_ = this.clusterList.length - 1;
      var _loc2_ = _loc4_;
      while(_loc2_ >= 0)
      {
         if(this.clusterList[_loc2_] == undefined)
         {
            return undefined;
         }
         _loc3_ += this.clusterList[_loc2_];
         _loc2_ = _loc2_ - 1;
      }
      return _loc3_;
   }
   function get length()
   {
      return this.clusterList.length;
   }
}
