class lol.core.quests.BringObjQuest implements lol.core.quests.QuestMission
{
   var obj_num;
   var diFlag = false;
   var num = 6;
   function BringObjQuest()
   {
   }
   function getMissionStatus()
   {
      var _loc3_ = "";
      var _loc2_ = 1;
      while(_loc2_ <= this.num)
      {
         if(this["obj_" + _loc2_] && this["item" + _loc2_].inited)
         {
            _loc3_ += "Найдено " + this.obj_num[_loc2_ - 1] + " " + this["item" + _loc2_].getProp("name") + "\r";
         }
         _loc2_ = _loc2_ + 1;
      }
      return _loc3_;
   }
   function initialize(obj)
   {
      var _loc2_ = 1;
      while(_loc2_ <= this.num)
      {
         this["obj_" + _loc2_] = obj.param["obj_" + _loc2_];
         this["obj_num_" + _loc2_] = obj.param["obj_num_" + _loc2_];
         this["mobs_" + _loc2_] = obj.param["mobs_" + _loc2_];
         if(this["obj_" + _loc2_])
         {
            this["item" + _loc2_] = lol.core.objects.ItemFactory.createPrototype(this["obj_" + _loc2_]);
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function update(obj)
   {
      var _loc4_ = new Object();
      var _loc3_ = obj.param.obj_num;
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         if(_loc3_[_loc2_] != this.obj_num[_loc2_])
         {
            _loc4_.currNum = _loc3_[_loc2_];
            _loc4_.num = this["obj_num_" + (_loc2_ + 1)];
            _loc4_.itemName = this["item" + (_loc2_ + 1)].getProp("name");
            _loc4_.lost = _loc3_[_loc2_] <= this.obj_num[_loc2_] ? true : false;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      this.obj_num = _loc3_;
      this.diFlag = true;
      return _loc4_;
   }
   function getDIFlag()
   {
      return this.diFlag;
   }
}
