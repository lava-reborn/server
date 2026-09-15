class lol.core.effects.EffectManager
{
   var dispatchEvent;
   var effect_list;
   var isGamer;
   var mobID;
   var old_effects_id;
   function EffectManager(_mobID)
   {
      lol.events.LEventDispatcher.initialize(this);
      this.mobID = _mobID;
      this.isGamer = _mobID == lol.core.player.Gamer.ID;
      this.effect_list = new Array();
      this.old_effects_id = new Array();
   }
   function e_list(obj)
   {
      if(obj.param.mobi_id != this.mobID)
      {
         return undefined;
      }
      this.effect_list = new Array();
      var _loc5_ = false;
      var _loc4_;
      var _loc2_;
      var _loc3_;
      if(obj.param.effects)
      {
         _loc4_ = obj.param.effects;
         _loc5_ = _loc4_.length > 0;
         _loc2_ = 0;
         while(_loc2_ < _loc4_.length)
         {
            _loc3_ = lol.core.effects.EffectsFactory.createRealEffect(this,_loc4_[_loc2_],false,this.mobID,false);
            this.effect_list.push(_loc3_);
            _loc2_ = _loc2_ + 1;
         }
         this.checkDebuffs();
         this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_EFFECTS));
         if(_loc5_)
         {
            this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.NEED_OPEN_FXPAN));
         }
      }
   }
   function checkDebuffs()
   {
      var _loc7_;
      var _loc9_ = false;
      var _loc3_ = 0;
      var _loc8_;
      var _loc2_;
      while(_loc3_ < this.effect_list.length)
      {
         _loc8_ = this.effect_list[_loc3_];
         if(this.effect_list[_loc3_].inited != false)
         {
            _loc7_ = this.effect_list[_loc3_].typeID;
            _loc9_ = false;
            if(this.old_effects_id.length == 0)
            {
               if(this.effect_list[_loc3_].isBuff() == false)
               {
                  this.dispatchEvent({type:lol.events.PlayerEvent.NEW_DEBUFF_EFFECT,mob_id:this.mobID,debuff_msg:this.effect_list[_loc3_].getDebuffString()});
               }
            }
            else
            {
               _loc2_ = 0;
               while(_loc2_ < this.old_effects_id.length)
               {
                  if(this.old_effects_id[_loc2_].inited == true && _loc7_ == this.old_effects_id[_loc2_])
                  {
                     if(this.effect_list[_loc3_].isBuff() == false)
                     {
                        this.dispatchEvent({type:lol.events.PlayerEvent.NEW_DEBUFF_EFFECT,mob_id:this.mobID,debuff_msg:this.effect_list[_loc3_].getDebuffString()});
                     }
                  }
                  _loc2_ = _loc2_ + 1;
               }
            }
         }
         _loc3_ = _loc3_ + 1;
      }
      this.old_effects_id.splice(0);
      _loc3_ = 0;
      while(_loc3_ < this.effect_list.length)
      {
         if(this.effect_list[_loc3_].inited == true)
         {
            this.old_effects_id.push(this.effect_list[_loc3_].typeID);
         }
         _loc3_ = _loc3_ + 1;
      }
   }
   function getFXArrayLength()
   {
      if(this.effect_list)
      {
         return this.effect_list.length;
      }
      return undefined;
   }
   function getEffect(i)
   {
      if(i >= 0 && i < this.effect_list.length)
      {
         return this.effect_list[i];
      }
      return undefined;
   }
   function onEffectUpdate(effect)
   {
      var _loc4_ = false;
      var _loc2_ = 0;
      while(_loc2_ < this.effect_list.length)
      {
         if(effect.typeID == this.effect_list[_loc2_].typeID)
         {
            this.effect_list[_loc2_].clone(effect);
            _loc4_ = true;
            break;
         }
         _loc2_ = _loc2_ + 1;
      }
      if(_loc4_)
      {
         this.checkDebuffs();
         this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_ONE_EFFECT));
      }
   }
}
