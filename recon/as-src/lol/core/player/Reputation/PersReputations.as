class lol.core.player.Reputation.PersReputations
{
   var _reputations;
   var dispatchEvent;
   static var INCREASE_REP_LEVEL = "INCREASE_REP_LEVEL";
   static var INCREASE_REPUTATION = "INCREASE_REPUTATION";
   var factionMaxCount = 1;
   function PersReputations()
   {
      lol.events.LEventDispatcher.initialize(this);
      this._reputations = new Array();
      var _loc2_ = 0;
      while(_loc2_ < this.factionMaxCount)
      {
         this._reputations[_loc2_] = new lol.core.player.Reputation.ReputationObject();
         this._reputations[_loc2_].id = _loc2_;
         this._reputations[_loc2_].title = "Навык бойца";
         this._reputations[_loc2_].addEventListener(lol.core.player.Reputation.ReputationObject.INCREASE_REPUTATION,this,this.increase_rep_func);
         this._reputations[_loc2_].addEventListener(lol.core.player.Reputation.ReputationObject.INCREASE_REP_LEVEL,this,this.increase_rep_level_func);
         _loc2_ = _loc2_ + 1;
      }
      this.init();
   }
   function init()
   {
   }
   function getReputation(index)
   {
      return this._reputations[index];
   }
   function updateReputations(reputations)
   {
      var _loc4_;
      var _loc2_ = 0;
      while(_loc2_ < reputations.length)
      {
         if(this._reputations[_loc2_].id != undefined)
         {
            this._reputations[_loc2_].xp_reputation = reputations[_loc2_];
            _loc4_ = reputations[_loc2_];
         }
         else
         {
            trace("REP.reputation with i = " + _loc2_ + " - not found");
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function increase_rep_func(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.id;
      var _loc5_ = _loc2_.title;
      var _loc3_ = obj.value;
      this.dispatchEvent({type:lol.core.player.Reputation.ReputationObject.INCREASE_REPUTATION,id:_loc4_,title:_loc5_,value:_loc3_});
   }
   function increase_rep_level_func(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.id;
      var _loc5_ = _loc2_.title;
      var _loc3_ = obj.value;
      this.dispatchEvent({type:lol.core.player.Reputation.ReputationObject.INCREASE_REP_LEVEL,id:_loc4_,title:_loc5_,value:_loc3_});
   }
}
