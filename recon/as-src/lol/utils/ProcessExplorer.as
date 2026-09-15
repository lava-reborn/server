class lol.utils.ProcessExplorer
{
   static var _ref;
   static var processList = new Array();
   function ProcessExplorer()
   {
      lol.events.LEventDispatcher.initialize(this);
   }
   static function create()
   {
      lol.utils.ProcessExplorer._ref = new lol.utils.ProcessExplorer();
      lol.utils.ProcessExplorer.start();
   }
   static function callProcess(name, spt)
   {
      if(!lol.utils.ProcessExplorer.existProcess(name))
      {
         lol.utils.ProcessExplorer.processList.push({name:name,spt:spt});
         lol.utils.ProcessExplorer.processList.sortOn("spt",Array.NUMERIC);
      }
   }
   static function existProcess(name)
   {
      var _loc1_ = 0;
      while(_loc1_ < lol.utils.ProcessExplorer.processList.length)
      {
         if(lol.utils.ProcessExplorer.processList[_loc1_].name == name)
         {
            return true;
         }
         _loc1_ = _loc1_ + 1;
      }
      return false;
   }
   static function clearList()
   {
      lol.utils.ProcessExplorer._ref.dispatchEvent({type:"refreshList",list:lol.utils.ProcessExplorer.processList});
      lol.utils.ProcessExplorer.processList = new Array();
   }
   static function start()
   {
      lol.utils.ProcessExplorer._ref.interval = setInterval(lol.utils.ProcessExplorer.clearList,1000);
   }
   static function pause()
   {
      clearInterval(lol.utils.ProcessExplorer._ref.interval);
   }
}
