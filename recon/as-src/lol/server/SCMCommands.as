class lol.server.SCMCommands
{
   var currentTime;
   var sequence;
   static var beacon_mc;
   static var instance;
   static var singletonCreation;
   function SCMCommands()
   {
      if(!lol.server.SCMCommands.singletonCreation)
      {
         throw new Error("ERROR:Singleton! call getInstance");
      }
      this.init();
   }
   static function getInstance()
   {
      if(!lol.server.SCMCommands.instance)
      {
         lol.server.SCMCommands.singletonCreation = true;
         lol.server.SCMCommands.instance = new lol.server.SCMCommands();
         lol.server.SCMCommands.singletonCreation = false;
      }
      return lol.server.SCMCommands.instance;
   }
   function init()
   {
      lol.server.SCMCommands.beacon_mc = _root.createEmptyMovieClip("beacon_mc",-3);
      lol.server.SCMCommands.beacon_mc.onEnterFrame = mx.utils.Delegate.create(this,this.run);
      this.sequence = new Array();
   }
   function add(c)
   {
      this.sequence.push(c);
   }
   function run()
   {
      this.currentTime = getTimer();
      this.executeNextCommand();
   }
   function executeNextCommand()
   {
      if(this.sequence.length == 0)
      {
         return undefined;
      }
      var _loc2_ = lol.server.incmess.SCCommand(this.sequence.shift());
      if(_loc2_ == null)
      {
         return undefined;
      }
      _loc2_.execute();
      if(getTimer() - this.currentTime < 40)
      {
         this.executeNextCommand();
      }
   }
}
