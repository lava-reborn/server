class lol.core.player.Mob extends lol.core.player.Entity
{
   var attackPhrases;
   var deathPhrases;
   var detectPhrases;
   var equipment;
   var id;
   var idlePhrases;
   var isMob;
   var playerInfo;
   var runPhrases;
   static var staticID = "Mob";
   static var RTYPE = 0;
   function Mob(ID)
   {
      super(ID);
      if(lol.core.Master.getInstance().currentState == lol.core.Master.LOCAL_STATE)
      {
         this.equipment.getStuff(3,this.id);
      }
      this.isMob = true;
   }
   function userInfo(obj)
   {
      super.userInfo(obj);
      this.playerInfo.persType = obj.param.res;
      this.idlePhrases = obj.param.m_idle;
      this.detectPhrases = obj.param.m_detect;
      this.attackPhrases = obj.param.m_attack;
      this.runPhrases = obj.param.m_run;
      this.deathPhrases = obj.param.m_death;
   }
   function getIdlePhrase()
   {
      return this.getRandomPhrase(this.idlePhrases);
   }
   function getDetectPhrase()
   {
      return this.getRandomPhrase(this.detectPhrases);
   }
   function getAttackPhrase()
   {
      return this.getRandomPhrase(this.attackPhrases);
   }
   function getRunPhrase()
   {
      return this.getRandomPhrase(this.runPhrases);
   }
   function getDeathPhrase()
   {
      return this.getRandomPhrase(this.deathPhrases);
   }
   function getRandomPhrase(arr)
   {
      var _loc2_;
      var _loc3_;
      if(arr && arr.length > 0)
      {
         if(arr.length > 1)
         {
            _loc3_ = random(arr.length - 1);
            _loc2_ = String(arr.splice(_loc3_,1));
            arr.push(_loc2_);
         }
         else
         {
            _loc2_ = arr[0];
         }
      }
      else
      {
         _loc2_ = null;
      }
      return _loc2_;
   }
}
