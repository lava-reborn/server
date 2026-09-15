class lol.utils.ExtProfiler
{
   static var attentionArray;
   static var processArray;
   static var timeArray;
   static var _ref = new lol.utils.ExtProfiler();
   static var attentionTime = 20;
   static var totalCallTime = 0;
   function ExtProfiler()
   {
      lol.events.LEventDispatcher.initialize(this);
      lol.utils.ExtProfiler.processArray = new Array();
      lol.utils.ExtProfiler.timeArray = new Array();
      lol.utils.ExtProfiler.attentionArray = new Array();
   }
   static function startProcess(name, subname)
   {
      var _loc4_ = getTimer();
      var _loc5_;
      var _loc6_;
      if(!lol.utils.ExtProfiler.processArray[name])
      {
         lol.utils.ExtProfiler.processArray[name] = new Array();
         lol.utils.ExtProfiler.processArray[name].all = lol.utils.ExtProfiler.createProcess(name);
      }
      _loc6_ = lol.utils.ExtProfiler.processArray[name].all;
      if(subname)
      {
         if(!lol.utils.ExtProfiler.processArray[name][subname])
         {
            lol.utils.ExtProfiler.processArray[name][subname] = lol.utils.ExtProfiler.createProcess(subname);
         }
      }
      _loc5_ = lol.utils.ExtProfiler.processArray[name][subname];
      _loc5_.callArray.push(_loc4_);
      var _loc3_ = [name,subname];
      return _loc3_;
   }
   static function createProcess(name)
   {
      var _loc1_ = new Object();
      _loc1_.name = name;
      _loc1_.callArray = new Array();
      _loc1_.totalTime = 0;
      return _loc1_;
   }
   static function stopProcess(id, comment)
   {
      var _loc7_ = getTimer();
      var _loc4_ = id[0];
      var _loc8_ = id[1];
      var _loc1_;
      _loc1_ = lol.utils.ExtProfiler.processArray[_loc4_][_loc8_];
      var _loc6_ = _loc1_.callArray.pop();
      var _loc2_ = _loc7_ - _loc6_;
      _loc1_.callArray.push([_loc6_,_loc2_,comment]);
      _loc1_.count = _loc1_.callArray.length;
      _loc1_.pname = _loc4_;
      _loc1_.totalTime += _loc2_;
      if(_loc2_ > lol.utils.ExtProfiler.attentionTime)
      {
         lol.utils.ExtProfiler.addAttention(_loc1_);
      }
      var _loc3_ = lol.utils.ExtProfiler.processArray[_loc4_].all;
      _loc3_.callArray.push([_loc6_,_loc2_]);
      _loc3_.count = _loc3_.callArray.length;
      _loc3_.totalTime += _loc2_;
      var _loc5_ = Math.floor(_loc7_ / 100);
      if(!lol.utils.ExtProfiler.timeArray[_loc5_])
      {
         lol.utils.ExtProfiler.timeArray[_loc5_] = new Array();
      }
      lol.utils.ExtProfiler.timeArray[_loc5_].push(_loc1_);
      lol.utils.ExtProfiler.totalCallTime += _loc2_;
   }
   static function addAttention(process)
   {
      var _loc1_ = process.name;
      if(!lol.utils.ExtProfiler.attentionArray[_loc1_])
      {
         lol.utils.ExtProfiler.attentionArray[_loc1_] = lol.utils.ExtProfiler.createProcess(_loc1_);
      }
      var _loc3_ = lol.utils.ExtProfiler.attentionArray[_loc1_];
      var _loc4_ = process.callArray[process.callArray.length - 1];
      _loc3_.comment = !process.comment ? undefined : process.comment;
      _loc3_.callArray.push(_loc4_);
   }
   static function getTotalTime()
   {
      return getTimer();
   }
   static function getTotalCallTime()
   {
      return lol.utils.ExtProfiler.totalCallTime;
   }
}
