class lol.core.player.Reputation.ReputationObject
{
   var _value_bonus;
   var _xp_reputation;
   var dispatchEvent;
   var frac_rep_Arr;
   var xp_max_rep;
   static var rank_level;
   static var INCREASE_REP_LEVEL = "INCREASE_REP_LEVEL";
   static var INCREASE_REPUTATION = "INCREASE_REPUTATION";
   function ReputationObject()
   {
      lol.events.LEventDispatcher.initialize(this);
      this.frac_rep_Arr = new Array();
      lol.core.player.Reputation.ReputationObject.rank_level = new Array();
      lol.core.player.Reputation.ReputationObject.rank_level[0] = [0,100,"Странник"];
      lol.core.player.Reputation.ReputationObject.rank_level[1] = [100,200,"Следопыт"];
      lol.core.player.Reputation.ReputationObject.rank_level[2] = [200,400,"Охотник"];
      lol.core.player.Reputation.ReputationObject.rank_level[3] = [400,800,"Преследователь"];
      lol.core.player.Reputation.ReputationObject.rank_level[4] = [800,1600,"Налетчик"];
      lol.core.player.Reputation.ReputationObject.rank_level[5] = [1600,3200,"Стрелок"];
      lol.core.player.Reputation.ReputationObject.rank_level[6] = [3200,6400,"Пустынный рейнджер"];
      lol.core.player.Reputation.ReputationObject.rank_level[7] = [6400,12800,"Мститель"];
      lol.core.player.Reputation.ReputationObject.rank_level[8] = [12800,25600,"Ассасин"];
   }
   function set value_bonus(num)
   {
      if(this._value_bonus != num && num != 0)
      {
         this.dispatchEvent({type:lol.core.player.Reputation.ReputationObject.INCREASE_REP_LEVEL,value:num});
      }
      this._value_bonus = num;
   }
   function get value_bonus()
   {
      return this._value_bonus;
   }
   function get currentValue()
   {
      var _loc2_ = Math.round(this._xp_reputation * 100 / this.xp_max_rep);
      return _loc2_;
   }
   function set xp_reputation(value)
   {
      var _loc4_;
      if(value > this._xp_reputation && this._xp_reputation != undefined)
      {
         _loc4_ = value - this._xp_reputation;
         this.dispatchEvent({type:lol.core.player.Reputation.ReputationObject.INCREASE_REPUTATION,value:_loc4_});
      }
      this._xp_reputation = value;
      for(var _loc2_ in lol.core.player.Reputation.ReputationObject.rank_level)
      {
         if(this._xp_reputation >= lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][0] && this._xp_reputation < lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][1])
         {
            this.xp_max_rep = lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][1];
            this.value_bonus = _loc2_;
            break;
         }
      }
   }
   function get xp_reputations()
   {
      return this._xp_reputation;
   }
   function get level()
   {
      return this.value_bonus;
   }
   function get levelString()
   {
      var _loc2_ = this.repString(this._xp_reputation);
      return _loc2_;
   }
   function estimateReputation()
   {
      return this.xp_max_rep - this._xp_reputation;
   }
   function nextLevel()
   {
      var _loc3_;
      var _loc4_;
      var _loc5_;
      var _loc2_ = 0;
      while(_loc2_ < lol.core.player.Reputation.ReputationObject.rank_level.length)
      {
         if(this._xp_reputation >= lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][0] && this._xp_reputation < lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][1])
         {
            _loc3_ = lol.core.player.Reputation.ReputationObject.rank_level[_loc2_ + 1][2];
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      if(_loc3_)
      {
         return _loc3_;
      }
      return "Достигнуто максимальное звание";
   }
   function repString(num)
   {
      var _loc5_;
      var _loc6_;
      var _loc3_;
      var _loc7_;
      var _loc2_ = 0;
      while(_loc2_ < lol.core.player.Reputation.ReputationObject.rank_level.length)
      {
         if(num >= lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][0] && num < lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][1])
         {
            _loc7_ = _loc2_;
            _loc5_ = lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][2];
            _loc6_ = lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][0];
            _loc3_ = lol.core.player.Reputation.ReputationObject.rank_level[_loc2_][1];
            this.xp_max_rep = _loc3_;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      var _loc8_ = Math.round(num * 100 / _loc3_);
      _loc5_ = "Звание: " + _loc5_ + ", " + num + " из " + _loc3_ + " ( " + _loc8_ + "% )";
      return _loc5_;
   }
}
