class lol.core.quests.KillMobQuest implements lol.core.quests.QuestMission
{
   var kill_num;
   var mobs_kill;
   var num_kill;
   var diFlag = false;
   function KillMobQuest()
   {
   }
   function getMissionStatus()
   {
      var _loc3_ = "";
      var _loc2_ = 0;
      while(_loc2_ < this.mobs_kill.length)
      {
         _loc3_ += "Убито " + this.kill_num[_loc2_] + " целей из " + this.num_kill[_loc2_] + "\r";
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function initialize(obj)
   {
      this.mobs_kill = obj.param.mobs_kill;
      this.num_kill = obj.param.num_kill;
   }
   function update(obj)
   {
      var _loc4_ = new Object();
      var _loc3_ = obj.param.kill_num;
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_] != this.kill_num[_loc2_])
         {
            _loc4_.currNum = _loc3_[_loc2_];
            _loc4_.num = this.num_kill[_loc2_];
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.kill_num = _loc3_;
      this.diFlag = true;
      return _loc4_;
   }
   function getDIFlag()
   {
      return this.diFlag;
   }
}
