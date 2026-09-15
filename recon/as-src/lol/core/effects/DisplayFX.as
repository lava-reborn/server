class lol.core.effects.DisplayFX extends MovieClip
{
   var buff_ActualSigns;
   var buff_EstimateTimes;
   var buff_MCs;
   var buff_StartTimers;
   var buff_length;
   var core_mc;
   var debuff_ActualSigns;
   var debuff_EstimateTimes;
   var debuff_MCs;
   var debuff_StartTimers;
   var debuff_length;
   var effectsTimer;
   var master;
   static var BUFF_WIDTH = 44;
   function DisplayFX()
   {
      super();
      this.effectsTimer = NaN;
      this.master = lol.core.Master.getInstance();
      this.core_mc = this;
      this.init();
   }
   function init()
   {
      this.buff_MCs = new Array();
      this.debuff_MCs = new Array();
      this.buff_StartTimers = new Array();
      this.debuff_StartTimers = new Array();
      this.buff_EstimateTimes = new Array();
      this.debuff_EstimateTimes = new Array();
      this.buff_ActualSigns = new Array();
      this.debuff_ActualSigns = new Array();
      this.buff_length = 0;
      this.debuff_length = 0;
      var _loc2_ = this.master.gamer;
      if(this.master.gamer)
      {
         _loc2_.effects.addEventListener(lol.events.PlayerEvent.UPDATE_EFFECTS,this,this.effectsUpdate);
         _loc2_.effects.addEventListener(lol.events.PlayerEvent.UPDATE_ONE_EFFECT,this,this.oneEffectUpdate);
      }
      this.effectsUpdate();
   }
   function kill()
   {
      this.ResetActualArrays();
      this.ClearOldEffects();
   }
   function ResetActualArrays()
   {
      var _loc2_;
      for(_loc2_ in this.buff_ActualSigns)
      {
         this.buff_ActualSigns[_loc2_] = false;
      }
      for(_loc2_ in this.debuff_ActualSigns)
      {
         this.debuff_ActualSigns[_loc2_] = false;
      }
   }
   function ClearOldEffects()
   {
      var _loc2_;
      for(_loc2_ in this.buff_ActualSigns)
      {
         if(!this.buff_ActualSigns[_loc2_])
         {
            if(this.buff_MCs[_loc2_] != undefined)
            {
               this.buff_EstimateTimes[_loc2_] = undefined;
               this.buff_StartTimers[_loc2_] = undefined;
               this.buff_MCs[_loc2_].effect = undefined;
               this.buff_MCs[_loc2_].removeMovieClip();
               this.buff_MCs[_loc2_] = undefined;
               this.buff_length = this.buff_length - 1;
            }
         }
      }
      for(_loc2_ in this.debuff_ActualSigns)
      {
         if(!this.debuff_ActualSigns[_loc2_])
         {
            if(this.debuff_MCs[_loc2_] != undefined)
            {
               this.debuff_EstimateTimes[_loc2_] = undefined;
               this.debuff_StartTimers[_loc2_] = undefined;
               this.debuff_MCs[_loc2_].effect = undefined;
               this.debuff_MCs[_loc2_].removeMovieClip();
               this.debuff_MCs[_loc2_] = undefined;
               this.debuff_length = this.debuff_length - 1;
            }
         }
      }
   }
   function effectsUpdate(obj)
   {
      var _loc4_;
      var _loc8_;
      var _loc6_ = this.master.gamer;
      var _loc7_ = _loc6_.id;
      this.ResetActualArrays();
      this.ClearOldEffects();
      _loc4_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc3_;
      while(_loc4_ < _loc6_.effects.getFXArrayLength())
      {
         _loc2_ = _loc6_.effects.getEffect(_loc4_);
         if(_loc2_)
         {
            _loc5_ = _loc2_.typeID;
            _loc3_ = _loc2_.isBuff();
            if(_loc3_)
            {
               if(this.buff_MCs[_loc5_] != undefined)
               {
                  this.UpdateEffect(_loc2_,this.buff_MCs,this.buff_StartTimers,this.buff_EstimateTimes,this.buff_ActualSigns);
               }
               else
               {
                  this.CreateEffect(_loc2_,_loc3_);
               }
            }
            else if(this.debuff_MCs[_loc5_] != undefined)
            {
               this.UpdateEffect(_loc2_,this.debuff_MCs,this.debuff_StartTimers,this.debuff_EstimateTimes,this.debuff_ActualSigns);
            }
            else
            {
               this.CreateEffect(_loc2_,_loc3_);
            }
         }
         _loc4_ = _loc4_ + 1;
      }
   }
   function oneEffectUpdate(obj)
   {
      var _loc4_;
      var _loc8_;
      var _loc6_ = this.master.gamer;
      var _loc7_ = _loc6_.id;
      _loc4_ = 0;
      var _loc2_;
      var _loc5_;
      var _loc3_;
      while(_loc4_ < _loc6_.effects.getFXArrayLength())
      {
         _loc2_ = _loc6_.effects.getEffect(_loc4_);
         if(_loc2_)
         {
            _loc5_ = _loc2_.typeID;
            _loc3_ = _loc2_.isBuff();
            if(_loc3_)
            {
               if(this.buff_MCs[_loc5_] != undefined)
               {
                  this.UpdateEffect(_loc2_,this.buff_MCs,this.buff_StartTimers,this.buff_EstimateTimes,this.buff_ActualSigns);
               }
               else
               {
                  this.CreateEffect(_loc2_,_loc3_);
               }
            }
            else if(this.debuff_MCs[_loc5_] != undefined)
            {
               this.UpdateEffect(_loc2_,this.debuff_MCs,this.debuff_StartTimers,this.debuff_EstimateTimes,this.debuff_ActualSigns);
            }
            else
            {
               this.CreateEffect(_loc2_,_loc3_);
            }
         }
         _loc4_ = _loc4_ + 1;
      }
   }
   function CreateEffect(effect, is_buff)
   {
      var _loc3_ = effect.typeID;
      if(effect.effect_time == undefined)
      {
         return undefined;
      }
      if(effect.work_time == undefined)
      {
         return undefined;
      }
      if(effect.register_time == undefined)
      {
         return undefined;
      }
      var _loc7_ = this.core_mc.getNextHighestDepth();
      var _loc2_ = this.core_mc.attachMovie("FX_Shortcut","buff_" + _loc3_,_loc7_);
      _loc2_.effect = effect;
      _loc2_._width = lol.core.effects.DisplayFX.BUFF_WIDTH;
      _loc2_.EstimateTime.autoSize = true;
      _loc2_.onRollOver = mx.utils.Delegate.create(this,function()
      {
         this.rollOverBack(effect);
      }
      );
      _loc2_.onRollOut = mx.utils.Delegate.create(this,function()
      {
         this.rollOutBack(effect);
      }
      );
      var _loc8_ = lol.services.SSEmulator.getEffectIcon(effect.res_icon);
      _loc2_.EffectIcon = lol.display.DisplaySprite.create(_loc2_.EffectIcon,"EffectIcon",0);
      _loc2_.EffectIcon.display(effect.typeID + "_effect_icon",_loc8_);
      if(is_buff)
      {
         _loc2_._x = 0;
         _loc2_._y = _loc2_._height * this.buff_length;
      }
      else
      {
         _loc2_._x = 35;
         _loc2_._y = _loc2_._height * this.debuff_length;
      }
      _loc2_._visible = true;
      var _loc10_ = effect.effect_time;
      var _loc9_ = effect.work_time;
      var _loc4_ = Number(_loc9_ - _loc10_);
      var _loc5_ = getTimer();
      _loc4_ -= _loc5_ - effect.register_time - 1000;
      if(!isNaN(_loc4_))
      {
         _loc2_.EstimateTime.text = this.GetShortDuration(_loc4_);
         if(is_buff)
         {
            this.buff_StartTimers[_loc3_] = _loc5_;
            this.buff_EstimateTimes[_loc3_] = _loc4_;
         }
         else
         {
            this.debuff_StartTimers[_loc3_] = _loc5_;
            this.debuff_EstimateTimes[_loc3_] = _loc4_;
         }
         if(this.effectsTimer == NaN)
         {
            this.effectsTimer = setInterval(this,"updateEffectMCs",100);
         }
      }
      else
      {
         _loc2_.EstimateTime.text = "--:--";
      }
      if(is_buff)
      {
         this.buff_ActualSigns[_loc3_] = true;
         this.buff_MCs[_loc3_] = _loc2_;
         this.buff_length = this.buff_length + 1;
      }
      else
      {
         this.debuff_ActualSigns[_loc3_] = true;
         this.debuff_MCs[_loc3_] = _loc2_;
         this.debuff_length = this.debuff_length + 1;
      }
   }
   function UpdateEffect(effect, MC_array, StartTimers_array, EstimateTime_array, actualSigns_array)
   {
      var _loc6_ = effect.effect_time;
      var _loc5_ = effect.work_time;
      var _loc3_ = _loc5_ - _loc6_;
      var _loc8_ = StartTimers_array[effect.typeID];
      var _loc4_ = getTimer();
      _loc3_ -= _loc4_ - effect.register_time - 1000;
      if(!isNaN(_loc3_))
      {
         MC_array[effect.typeID].EstimateTime.text = this.GetShortDuration(_loc3_);
         StartTimers_array[effect.typeID] = _loc4_;
         EstimateTime_array[effect.typeID] = _loc3_;
         if(this.effectsTimer == NaN)
         {
            this.effectsTimer = setInterval(this,"updateEffectMCs",100);
         }
         actualSigns_array[effect.typeID] = true;
      }
   }
   function updateEffectMCs()
   {
      var _loc2_;
      var _loc3_;
      var _loc5_ = getTimer();
      var _loc4_;
      for(_loc2_ in this.buff_ActualSigns)
      {
         if(this.buff_ActualSigns[_loc2_] && this.buff_MCs[_loc2_])
         {
            _loc4_ = Math.floor(_loc5_ - this.buff_StartTimers[_loc2_]);
            if(_loc4_ >= this.buff_EstimateTimes[_loc2_])
            {
               this.buff_MCs[_loc2_].EstimateTime.text = "--:--";
            }
            else
            {
               _loc3_ = this.buff_EstimateTimes[_loc2_] - _loc4_;
               this.buff_MCs[_loc2_].EstimateTime.text = this.GetShortDuration(_loc3_);
            }
         }
      }
      for(_loc2_ in this.debuff_ActualSigns)
      {
         if(this.debuff_ActualSigns[_loc2_] && this.debuff_MCs[_loc2_])
         {
            _loc4_ = Math.floor(_loc5_ - this.debuff_StartTimers[_loc2_]);
            if(_loc4_ >= this.debuff_EstimateTimes[_loc2_])
            {
               this.debuff_MCs[_loc2_].EstimateTime.text = "--:--";
            }
            else
            {
               _loc3_ = this.debuff_EstimateTimes[_loc2_] - _loc4_;
               this.debuff_MCs[_loc2_].EstimateTime.text = this.GetShortDuration(_loc3_);
            }
         }
      }
   }
   function GetShortDuration(milliseconds)
   {
      var _loc5_;
      var _loc1_ = Math.floor(milliseconds / 1000);
      var _loc3_;
      var _loc2_;
      var _loc8_;
      var _loc4_;
      var _loc7_;
      var _loc6_;
      var _loc9_;
      if(_loc1_ > 60)
      {
         _loc3_ = Math.floor(_loc1_ / 60);
         if(_loc1_ > 3600)
         {
            _loc2_ = Math.floor(_loc1_ / 3600);
            _loc8_ = _loc2_ <= 9 ? "0" + _loc2_.toString() : _loc2_.toString();
            _loc4_ = Math.floor((_loc1_ - _loc2_ * 3600) / 60);
            _loc7_ = _loc4_ <= 9 ? "0" + _loc4_.toString() : _loc4_.toString();
            _loc6_ = Math.floor(_loc1_ - _loc2_ * 3600 - _loc4_ * 60);
            _loc9_ = _loc6_ <= 9 ? "0" + _loc6_.toString() : _loc6_.toString();
            _loc5_ = _loc8_ + ":" + _loc7_ + " : " + _loc9_;
         }
         else
         {
            _loc6_ = _loc1_ - _loc3_ * 60;
            _loc7_ = _loc3_ <= 9 ? "0" + _loc3_ : _loc3_;
            if(_loc6_ > 9)
            {
               _loc9_ = _loc6_.toString();
            }
            else
            {
               _loc9_ = "0" + _loc6_.toString();
            }
            _loc5_ = _loc7_ + ":" + _loc9_;
         }
      }
      else
      {
         _loc9_ = _loc1_ <= 9 ? "0" + _loc1_ : _loc1_;
         _loc5_ = "00:" + _loc1_;
      }
      return _loc5_;
   }
   function rollOverBack(effect)
   {
      lol.gpui.AnnotationManager.createOneEffectAnnotation(effect,this._xmouse,lol.core.effects.DisplayFX.BUFF_WIDTH - this._xmouse,this._ymouse);
   }
   function rollOutBack(effect)
   {
      lol.gpui.AnnotationManager.clear();
   }
}
